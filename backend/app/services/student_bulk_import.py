import csv
import io
import re
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from app.constants import GENDERS, NATIONALITIES, RELIGIONS
from app.models.classes import AcademicClass, AcademicClassStream, Class, Stream, Term
from app.models.school_settings import AcademicYear
from app.models.students import (
    ClassRegister,
    Student,
    find_duplicate_student,
    normalize_guardian_contact,
    normalize_student_name,
)
from app.selectors.school_settings import get_current_academic_year
from app.validators import normalize_uganda_lin, validate_uganda_lin

from .students import BulkStudentRegistrationError, create_student_bill


HEADER_ALIASES = {
    "reg_no": {"reg no", "registration no", "student id", "id no"},
    "lin_number": {
        "lin",
        "lin number",
        "learner identification number",
        "learner id number",
    },
    "schoolpay_number": {
        "schoolpay",
        "schoolpay number",
        "school pay",
        "school pay number",
    },
    "residency_status": {
        "student type",
        "residency",
        "residency status",
        "day boarding",
        "day or boarding",
    },
    "student_name": {"student name", "name"},
    "gender": {"gender", "sex"},
    "birthdate": {"birthdate", "birth date", "date of birth", "dob"},
    "nationality": {"nationality", "country"},
    "religion": {"religion"},
    "address": {"address"},
    "guardian": {"guardian", "guardian name"},
    "relationship": {"relationship"},
    "contact": {"guardian contact", "contact", "guardian phone", "phone"},
    "academic_year": {"academic year", "year", "entry year"},
    "current_class": {"current class", "class", "class code"},
    "stream": {"stream"},
    "term": {"term", "term id", "term number"},
}


def _normalize_header(header):
    normalized = str(header or "").strip().lower().replace("_", " ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _find_header_row(rows):
    for idx, row in enumerate(rows):
        normalized = [_normalize_header(cell) for cell in row if str(cell).strip()]
        has_student_name = "student name" in normalized
        has_term = any(value == "term" or value.startswith("term ") for value in normalized)
        if has_student_name and has_term:
            return idx
    return None


def _build_field_positions(header_row):
    positions = {}
    for index, raw_header in enumerate(header_row):
        header = _normalize_header(raw_header)
        for canonical, aliases in HEADER_ALIASES.items():
            if header in aliases or any(header.startswith(f"{alias} ") for alias in aliases):
                positions[canonical] = index
                break
    return positions


def _parse_birthdate(raw_value, row_number):
    value = str(raw_value or "").strip()
    for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%m/%d/%y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(
        f"Row {row_number}: invalid birthdate '{value}'. Use YYYY-MM-DD (or dd/mm/yyyy)."
    )


def _resolve_academic_year(raw_value, row_number):
    value = str(raw_value or "").strip()
    if not value:
        year = get_current_academic_year()
        if not year:
            raise ValueError(f"Row {row_number}: no current academic year is configured.")
        return year

    year = AcademicYear.objects.filter(academic_year=value).first()
    if year:
        return year
    if value.isdigit():
        year = AcademicYear.objects.filter(id=int(value)).first()
        if year:
            return year
    raise ValueError(f"Row {row_number}: academic year '{value}' was not found.")


def _resolve_term(raw_value, academic_year, row_number):
    raw = str(raw_value or "").strip()
    if not raw:
        raise ValueError(f"Row {row_number}: term is required.")

    normalized = raw.lower().replace("term", "").replace(" ", "")
    term_number = {"i": "1", "ii": "2", "iii": "3"}.get(normalized, normalized)
    term = Term.objects.filter(academic_year=academic_year, term=term_number).first()
    if term:
        return term
    if raw.isdigit():
        term = Term.objects.filter(id=int(raw), academic_year=academic_year).first()
        if term:
            return term
    raise ValueError(
        f"Row {row_number}: term '{raw}' is invalid for academic year '{academic_year.academic_year}'."
    )


def _resolve_class(raw_value, row_number):
    value = str(raw_value or "").strip()
    if not value:
        raise ValueError(f"Row {row_number}: class is required.")
    klass = Class.objects.filter(code__iexact=value).first() or Class.objects.filter(name__iexact=value).first()
    if not klass:
        raise ValueError(f"Row {row_number}: class '{value}' was not found.")
    return klass


def _resolve_stream(raw_value, row_number):
    value = str(raw_value or "").strip()
    if not value:
        raise ValueError(f"Row {row_number}: stream is required.")
    stream = Stream.objects.filter(stream__iexact=value).first()
    if not stream:
        raise ValueError(f"Row {row_number}: stream '{value}' was not found.")
    return stream


def _normalize_gender(raw_value, row_number):
    value = str(raw_value or "").strip().lower()
    normalized = {"m": "M", "male": "M", "f": "F", "female": "F"}.get(value)
    if normalized:
        return normalized
    allowed = ", ".join(choice[0] for choice in GENDERS)
    raise ValueError(f"Row {row_number}: invalid gender '{raw_value}'. Allowed: {allowed}.")


def _normalize_choice(raw_value, row_number, field_name, allowed_choices):
    value = str(raw_value or "").strip()
    if not value:
        raise ValueError(f"Row {row_number}: {field_name} is required.")
    for allowed, _ in allowed_choices:
        if allowed.lower() == value.lower():
            return allowed
    allowed_values = ", ".join(choice[0] for choice in allowed_choices)
    raise ValueError(
        f"Row {row_number}: invalid {field_name} '{value}'. Allowed values: {allowed_values}."
    )


def _normalize_lin(raw_value, row_number):
    value = normalize_uganda_lin(raw_value)
    if not value:
        return None
    try:
        validate_uganda_lin(value)
    except ValidationError as exc:
        message = exc.messages[0] if exc.messages else str(exc)
        raise ValueError(f"Row {row_number}: invalid LIN '{value}'. {message}") from exc
    return value


def _normalize_schoolpay(raw_value):
    return str(raw_value or "").strip() or None


def _read_registration_csv(csv_source):
    source = getattr(csv_source, "file_name", None) or csv_source
    if not hasattr(source, "read"):
        raise BulkStudentRegistrationError(["The uploaded CSV file could not be read."])

    try:
        if hasattr(source, "seek"):
            source.seek(0)
        content = source.read()
    finally:
        if source is not csv_source and hasattr(source, "close"):
            source.close()

    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise BulkStudentRegistrationError([
                "The CSV must use UTF-8 encoding. Download a fresh template and save it as CSV UTF-8."
            ]) from exc

    return [
        row for row in csv.reader(io.StringIO(str(content)))
        if any(str(cell).strip() for cell in row)
    ]


def bulk_student_registration(csv_source):
    """Validate the complete CSV first, then create the whole import atomically."""
    errors = []
    prepared_rows = []
    seen_reg_numbers = set()
    seen_lins = set()
    seen_schoolpay_numbers = set()
    seen_identities = set()

    rows = _read_registration_csv(csv_source)
    if not rows:
        raise BulkStudentRegistrationError(["Uploaded CSV is empty."])

    header_index = _find_header_row(rows)
    if header_index is None:
        raise BulkStudentRegistrationError(["CSV header row not found. Use the provided template."])

    field_positions = _build_field_positions(rows[header_index])
    required_fields = [
        "student_name",
        "residency_status",
        "gender",
        "birthdate",
        "nationality",
        "religion",
        "address",
        "guardian",
        "relationship",
        "contact",
        "current_class",
        "stream",
        "term",
    ]
    missing_fields = [field for field in required_fields if field not in field_positions]
    if missing_fields:
        raise BulkStudentRegistrationError([
            f"CSV is missing required columns: {', '.join(missing_fields)}. Download a fresh template and try again."
        ])

    data_rows = rows[header_index + 1 :]
    if len(data_rows) > 2000:
        raise BulkStudentRegistrationError([
            "A single upload can contain at most 2,000 students. Split this file into smaller batches."
        ])

    for row_number, row in enumerate(data_rows, start=header_index + 2):
        try:
            def get_value(field_name):
                position = field_positions.get(field_name)
                if position is None or position >= len(row):
                    return ""
                return str(row[position]).strip()

            reg_no = get_value("reg_no")
            if reg_no:
                key = reg_no.casefold()
                if key in seen_reg_numbers:
                    raise ValueError(f"Row {row_number}: duplicate Reg No '{reg_no}' in CSV.")
                seen_reg_numbers.add(key)
                if Student.objects.filter(reg_no__iexact=reg_no).exists():
                    raise ValueError(f"Row {row_number}: student with Reg No '{reg_no}' already exists.")

            lin_number = _normalize_lin(get_value("lin_number"), row_number)
            if lin_number:
                key = lin_number.casefold()
                if key in seen_lins:
                    raise ValueError(f"Row {row_number}: duplicate LIN '{lin_number}' in CSV.")
                seen_lins.add(key)
                if Student.objects.filter(lin_number__iexact=lin_number).exists():
                    raise ValueError(f"Row {row_number}: LIN '{lin_number}' is already assigned to another student.")

            schoolpay_number = _normalize_schoolpay(get_value("schoolpay_number"))
            if schoolpay_number:
                key = schoolpay_number.casefold()
                if key in seen_schoolpay_numbers:
                    raise ValueError(
                        f"Row {row_number}: duplicate SchoolPay Number '{schoolpay_number}' in CSV."
                    )
                seen_schoolpay_numbers.add(key)
                if Student.objects.filter(schoolpay_number__iexact=schoolpay_number).exists():
                    raise ValueError(
                        f"Row {row_number}: SchoolPay Number '{schoolpay_number}' is already assigned to another student."
                    )

            student_name = get_value("student_name")
            if not student_name:
                raise ValueError(f"Row {row_number}: student name is required.")

            residency_status = _normalize_choice(
                get_value("residency_status"),
                row_number,
                "student type",
                Student.RESIDENCY_CHOICES,
            )
            academic_year = _resolve_academic_year(get_value("academic_year"), row_number)
            term = _resolve_term(get_value("term"), academic_year, row_number)
            current_class = _resolve_class(get_value("current_class"), row_number)
            stream = _resolve_stream(get_value("stream"), row_number)
            gender = _normalize_gender(get_value("gender"), row_number)
            birthdate = _parse_birthdate(get_value("birthdate"), row_number)
            nationality = _normalize_choice(get_value("nationality"), row_number, "nationality", NATIONALITIES)
            religion = _normalize_choice(get_value("religion"), row_number, "religion", RELIGIONS)

            contact = get_value("contact")
            identity = (
                normalize_student_name(student_name),
                birthdate,
                normalize_guardian_contact(contact),
            )
            if identity in seen_identities:
                raise ValueError(f"Row {row_number}: this student is duplicated in the CSV.")
            seen_identities.add(identity)

            duplicate = find_duplicate_student(
                student_name=student_name,
                birthdate=birthdate,
                contact=contact,
            )
            if duplicate:
                raise ValueError(
                    f"Row {row_number}: this student already exists as {duplicate.reg_no}."
                )

            academic_class = AcademicClass.objects.filter(
                academic_year=academic_year,
                Class=current_class,
                term=term,
            ).first()
            if not academic_class:
                raise ValueError(
                    f"Row {row_number}: no Academic Class setup for class '{current_class.code}' and term '{term.term}'."
                )

            class_stream = AcademicClassStream.objects.filter(
                academic_class=academic_class,
                stream=stream,
            ).first()
            if not class_stream:
                raise ValueError(
                    f"Row {row_number}: no class stream found for class '{current_class.code}' and stream '{stream.stream}'."
                )

            student_data = {
                "lin_number": lin_number,
                "schoolpay_number": schoolpay_number,
                "residency_status": residency_status,
                "student_name": student_name,
                "gender": gender,
                "birthdate": birthdate,
                "nationality": nationality,
                "religion": religion,
                "address": get_value("address"),
                "guardian": get_value("guardian"),
                "relationship": get_value("relationship"),
                "contact": contact,
                "academic_year": academic_year,
                "current_class": current_class,
                "stream": stream,
                "term": term,
            }
            if reg_no:
                student_data["reg_no"] = reg_no

            prepared_rows.append({
                "row_number": row_number,
                "student_data": student_data,
                "academic_class": academic_class,
                "class_stream": class_stream,
            })
        except ValueError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"Row {row_number}: unexpected error: {exc}")

    if errors:
        raise BulkStudentRegistrationError(errors)
    if not prepared_rows:
        raise BulkStudentRegistrationError(["The CSV does not contain any student rows."])

    created_count = 0
    try:
        with transaction.atomic():
            year_ids = sorted({row["student_data"]["academic_year"].pk for row in prepared_rows})
            list(
                AcademicYear.objects.select_for_update()
                .filter(pk__in=year_ids)
                .order_by("pk")
            )

            for prepared in prepared_rows:
                row_number = prepared["row_number"]
                student_data = prepared["student_data"]

                reg_no = student_data.get("reg_no")
                lin_number = student_data.get("lin_number")
                schoolpay_number = student_data.get("schoolpay_number")
                if reg_no and Student.objects.filter(reg_no__iexact=reg_no).exists():
                    raise BulkStudentRegistrationError([
                        f"Row {row_number}: student with Reg No '{reg_no}' already exists."
                    ])
                if lin_number and Student.objects.filter(lin_number__iexact=lin_number).exists():
                    raise BulkStudentRegistrationError([
                        f"Row {row_number}: LIN '{lin_number}' is already assigned to another student."
                    ])
                if schoolpay_number and Student.objects.filter(schoolpay_number__iexact=schoolpay_number).exists():
                    raise BulkStudentRegistrationError([
                        f"Row {row_number}: SchoolPay Number '{schoolpay_number}' is already assigned to another student."
                    ])

                duplicate = find_duplicate_student(
                    student_name=student_data["student_name"],
                    birthdate=student_data["birthdate"],
                    contact=student_data["contact"],
                )
                if duplicate:
                    raise BulkStudentRegistrationError([
                        f"Row {row_number}: this student already exists as {duplicate.reg_no}."
                    ])

                student = Student.objects.create(**student_data)
                ClassRegister.objects.create(
                    academic_class_stream=prepared["class_stream"],
                    student=student,
                )
                create_student_bill(student, prepared["academic_class"])
                created_count += 1
    except BulkStudentRegistrationError:
        raise
    except Exception as exc:
        raise BulkStudentRegistrationError([
            "No students were imported because the batch could not be committed. "
            f"Technical detail: {exc}"
        ]) from exc

    return {
        "created_count": created_count,
        "skipped_count": 0,
        "errors": [],
    }
