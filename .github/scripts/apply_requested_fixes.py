from pathlib import Path


def read(path):
    return Path(path).read_text()


def write(path, text):
    Path(path).write_text(text)


def replace(path, old, new, count=1):
    text = read(path)
    found = text.count(old)
    if found < count:
        raise RuntimeError(f"{path}: expected at least {count} occurrence(s), found {found}: {old[:100]!r}")
    write(path, text.replace(old, new, count))


# 1) Persist script verification mode in the database.
replace(
    'backend/app/models/results.py',
    'class ResultVerificationSetting(models.Model):\n    """Global settings for result verification rules."""\n    sample_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)',
    'class ResultVerificationSetting(models.Model):\n    """Global settings for result verification rules."""\n    enabled = models.BooleanField(\n        default=True,\n        help_text="When enabled, submitted marks must pass script verification before reporting.",\n    )\n    sample_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)',
)

replace(
    'backend/app/services/results_sampling.py',
    '        if not getattr(django_settings, "RESULT_VERIFICATION_ENABLED", True):',
    '        if not ResultVerificationSetting.get_settings().enabled:',
)

# 2) Let class teachers enter marks when they are actually the allocated subject teacher,
#    expose verification mode, and permit authorized users to toggle it.
replace(
    'backend/backend/marks_workspace.py',
    '    ResultModeSetting,\n    StaffAccount,',
    '    ResultModeSetting,\n    ResultVerificationSetting,\n    StaffAccount,',
)
replace(
    'backend/backend/marks_workspace.py',
    '    if role == "Class Teacher":\n        return "Class teachers cannot enter subject marks. Please contact the allocated subject teacher."\n    if role == "Teacher":\n        if assessment is None:\n            return None\n        if not _teacher_can_enter(_staff_member(request), assessment):\n            return "You can only enter marks for subjects allocated to you in this class."\n        return None',
    '    if role in {"Teacher", "Class Teacher"}:\n        if assessment is None:\n            return None\n        if not _teacher_can_enter(_staff_member(request), assessment):\n            return "You can only enter marks for subjects allocated to you in this class."\n        return None',
)
replace(
    'backend/backend/marks_workspace.py',
    '    if not request.user.is_superuser and role == "Teacher":\n        staff = _staff_member(request)\n        if not staff:\n            return queryset.none(), current_year, current_term\n        queryset = queryset.filter(\n            academic_class__class_streams__subjects__subject_teacher=staff,\n            academic_class__class_streams__subjects__subject_id=F("subject_id"),\n        ).distinct()\n    elif not request.user.is_superuser and role == "Class Teacher":\n        return queryset.none(), current_year, current_term\n    elif not request.user.is_superuser and role not in MARK_ENTRY_MANAGERS:',
    '    if not request.user.is_superuser and role in {"Teacher", "Class Teacher"}:\n        staff = _staff_member(request)\n        if not staff:\n            return queryset.none(), current_year, current_term\n        queryset = queryset.filter(\n            academic_class__class_streams__subjects__subject_teacher=staff,\n            academic_class__class_streams__subjects__subject_id=F("subject_id"),\n        ).distinct()\n    elif not request.user.is_superuser and role not in MARK_ENTRY_MANAGERS:',
)
replace(
    'backend/backend/marks_workspace.py',
    '            "role": role,\n            "can_enter": role != "Class Teacher" and not bool(denial),',
    '            "role": role,\n            "verification_enabled": bool(ResultVerificationSetting.get_settings().enabled),\n            "can_manage_verification": bool(request.user.is_superuser or role in MARK_ENTRY_MANAGERS),\n            "can_enter": not bool(denial),',
)
replace(
    'backend/backend/marks_workspace.py',
    '            "verification_enabled": True,',
    '            "verification_enabled": bool(ResultVerificationSetting.get_settings().enabled),',
)
replace(
    'backend/backend/marks_workspace.py',
    '\n\nclass MarksEntryAPIView(WorkspaceBaseAPIView):',
    '''\n\n    def post(self, request):
        role = _active_role(request)
        if not (request.user.is_superuser or role in MARK_ENTRY_MANAGERS):
            return Response(
                {"detail": "Your current role cannot change script verification settings."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if str(request.data.get("action") or "") != "set_verification_mode":
            return Response({"detail": "Choose a valid results settings action."}, status=status.HTTP_400_BAD_REQUEST)
        enabled = request.data.get("enabled")
        if not isinstance(enabled, bool):
            return Response({"detail": "Verification mode must be on or off."}, status=status.HTTP_400_BAD_REQUEST)
        setting = ResultVerificationSetting.get_settings()
        setting.enabled = enabled
        setting.save(update_fields=["enabled"])
        return Response({
            "verification_enabled": enabled,
            "detail": (
                "Script verification is ON. New result submissions must pass verification before reports."
                if enabled
                else "Script verification is OFF. New result submissions will be released directly to reports."
            ),
        })


class MarksEntryAPIView(WorkspaceBaseAPIView):''',
)

# 3) Fix the generic Next.js workspace proxy. Django serves lists at /workspace/resources/<resource>/.
replace(
    'frontend/app/api/workspace/[resource]/route.ts',
    'authenticatedBackendGet(`workspace/${encodeURIComponent(resource)}/${query ? `?${query}` : \'\'}`)',
    'authenticatedBackendGet(`workspace/resources/${encodeURIComponent(resource)}/${query ? `?${query}` : \'\'}`)',
)
replace(
    'frontend/app/api/workspace/[resource]/route.ts',
    '`workspace/${encodeURIComponent(resource)}/?${backendParams.toString()}`',
    '`workspace/resources/${encodeURIComponent(resource)}/?${backendParams.toString()}`',
)

# 4) Proxy POST requests used by the verification switch.
replace(
    'frontend/app/api/workspace/results/marks/route.ts',
    "export async function GET(request: Request) {\n  return proxyWorkspaceRequest('workspace/results/marks/', request);\n}\n",
    "export async function GET(request: Request) {\n  return proxyWorkspaceRequest('workspace/results/marks/', request);\n}\n\nexport async function POST(request: Request) {\n  return proxyWorkspaceRequest('workspace/results/marks/', request);\n}\n",
)

# 5) Add the verification toggle to the Results workspace.
replace(
    'frontend/components/reference/ReferenceResultsWorkspace.tsx',
    '  blocked_reason: string;\n  academic_year: string;',
    '  blocked_reason: string;\n  verification_enabled: boolean;\n  can_manage_verification: boolean;\n  academic_year: string;',
)
replace(
    'frontend/components/reference/ReferenceResultsWorkspace.tsx',
    '\nfunction MarksHubView({ dashboardPath }: { dashboardPath: string }) {',
    '''
function VerificationModeControl() {
  const toast = useToast();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [canManage, setCanManage] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch('/api/workspace/results/marks', { cache: 'no-store', signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Verification setting could not be loaded.');
        return payload as MarksHub;
      })
      .then((payload) => {
        setEnabled(Boolean(payload.verification_enabled));
        setCanManage(Boolean(payload.can_manage_verification));
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) toast.error('Verification setting unavailable', reason instanceof Error ? reason.message : 'Please try again.');
      });
    return () => controller.abort();
  }, [toast]);

  async function toggle() {
    if (enabled === null || !canManage || saving) return;
    const next = !enabled;
    setSaving(true);
    try {
      const response = await fetch('/api/workspace/results/marks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'set_verification_mode', enabled: next }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || 'Verification setting could not be changed.');
      setEnabled(Boolean(payload.verification_enabled));
      toast.success(next ? 'Script verification enabled' : 'Script verification disabled', payload.detail || 'Results workflow updated.');
    } catch (reason: unknown) {
      toast.error('Setting not changed', reason instanceof Error ? reason.message : 'Please try again.');
    } finally {
      setSaving(false);
    }
  }

  if (enabled === null) return null;

  return (
    <section className={`mb-4 flex flex-col gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center sm:justify-between ${enabled ? 'border-emerald-100 bg-emerald-50/70' : 'border-slate-200 bg-slate-50'}`}>
      <div className="flex items-start gap-3">
        <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}><ShieldCheck size={18} /></span>
        <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-extrabold text-[#10224A]">Script verification</h2><span className={`rounded-full px-2 py-1 text-[9px] font-extrabold ${enabled ? 'bg-emerald-600 text-white' : 'bg-slate-600 text-white'}`}>{enabled ? 'ON' : 'OFF'}</span></div><p className="mt-1 max-w-2xl text-[10px] leading-4 text-slate-600">{enabled ? 'Submitted marks must pass independent verification before they become available to reports.' : 'Submitted marks are verified automatically and released directly to reports.'}</p></div>
      </div>
      {canManage && <button type="button" role="switch" aria-checked={enabled} disabled={saving} onClick={() => void toggle()} className={`relative h-7 w-12 shrink-0 rounded-full transition ${enabled ? 'bg-emerald-600' : 'bg-slate-300'} disabled:opacity-60`}><span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${enabled ? 'left-6' : 'left-1'}`} /></button>}
    </section>
  );
}

function MarksHubView({ dashboardPath }: { dashboardPath: string }) {''',
)
replace(
    'frontend/components/reference/ReferenceResultsWorkspace.tsx',
    '''      {view === 'marks' ? (assessment > 0 ? <MarksEntrySheet assessmentId={assessment} dashboardPath={dashboardPath} /> : <MarksHubView dashboardPath={dashboardPath} />) : <ReferenceResourceView resource="results" />}''',
    '''      {view === 'marks'
        ? (assessment > 0 ? <MarksEntrySheet assessmentId={assessment} dashboardPath={dashboardPath} /> : <MarksHubView dashboardPath={dashboardPath} />)
        : <><VerificationModeControl /><ReferenceResourceView resource="results" /></>}''',
)

# 6) Hide fee balances/payments from teacher and other non-finance student profiles.
replace(
    'backend/backend/workspace_context.py',
    '    ClassSubjectAllocation,\n    Result,',
    '    ClassSubjectAllocation,\n    ParentAccess,\n    Result,',
)
replace(
    'backend/backend/workspace_context.py',
    '\ndef can_verify_results(request) -> bool:',
    '''
def can_view_student_finance(request, student) -> bool:
    role = canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)
    if request.user.is_superuser or role in {"Admin", "Head Teacher", "Bursar"}:
        return True
    if role == "Parent":
        return ParentAccess.objects.filter(
            user=request.user,
            student=student,
            is_active=True,
            is_verified=True,
            can_view_finance=True,
        ).exists()
    return False


def can_verify_results(request) -> bool:''',
)
replace(
    'backend/backend/workspace_context.py',
    '    results = list(student.results.select_related(',
    '    can_view_finance = can_view_student_finance(request, student)\n\n    results = list(student.results.select_related(',
)
replace(
    'backend/backend/workspace_context.py',
    '''    bills = list(student.bills.select_related("academic_class__Class", "academic_class__term").prefetch_related(
        "items", "payments", "applied_credits",
    ).order_by("-bill_date")[:50])''',
    '''    bills = list(student.bills.select_related("academic_class__Class", "academic_class__term").prefetch_related(
        "items", "payments", "applied_credits",
    ).order_by("-bill_date")[:50]) if can_view_finance else []''',
)
replace(
    'backend/backend/workspace_context.py',
    '    return {\n        "resource": "students", "id": student.pk, "eyebrow": "Student workspace",',
    '    payload = {\n        "resource": "students", "id": student.pk, "eyebrow": "Student workspace",',
)
replace(
    'backend/backend/workspace_context.py',
    '\n\n\ndef _staff_workspace(request, pk: int):',
    '''
    if not can_view_finance:
        payload["tabs"] = [tab for tab in payload["tabs"] if tab.get("key") != "fees"]
        payload["actions"] = [action for action in payload["actions"] if action.get("label") != "Open fee account"]
        payload["metrics"] = [metric for metric in payload["metrics"] if metric.get("label") not in {"Paid", "Outstanding"}]
    return payload



def _staff_workspace(request, pk: int):''',
)

# 7) Treat overpayment as reusable student credit once, not both a negative bill balance and credit.
replace(
    'backend/app/models/fees_payment.py',
    '        if balance < 0:\n            return "Credit"\n        if balance == 0 and (Decimal(self.net_amount_due) > 0 or paid > 0):',
    '        if balance <= 0 and (Decimal(self.net_amount_due) > 0 or paid > 0):',
)
replace(
    'backend/backend/student_finance.py',
    'from django.db.models import Q',
    'from django.db.models import Q, Sum',
)
replace(
    'backend/backend/student_finance.py',
    '    Payment,\n    StudentBill,',
    '    Payment,\n    SchoolSetting,\n    StudentBill,',
)
replace(
    'backend/backend/student_finance.py',
    '''def _status_for_bill(bill: StudentBill) -> str:
    return bill.payment_status_display


def _reconcile_overpayment_credit(bill: StudentBill) -> Decimal:
    """Keep the unused overpayment credit aligned with the bill's net amount due."""
    bill.refresh_from_db()
    overpayment = max(Decimal(bill.amount_paid) - Decimal(bill.net_amount_due), Decimal("0"))
    unused = StudentCredit.objects.filter(
        student=bill.student,
        original_bill=bill,
        description__icontains="overpayment credit",
        is_applied=False,
    ).order_by("id")

    first = unused.first()
    if overpayment > 0:
        if first:
            first.amount = overpayment
            first.description = f"Overpayment credit from bill #{bill.id}"
            first.save(update_fields=["amount", "description"])
            unused.exclude(pk=first.pk).delete()
        else:
            StudentCredit.objects.create(
                student=bill.student,
                amount=overpayment,
                description=f"Overpayment credit from bill #{bill.id}",
                original_bill=bill,
                is_applied=False,
            )
    else:
        unused.delete()
    return overpayment
''',
    '''def _status_for_bill(bill: StudentBill) -> str:
    return bill.payment_status_display


def _school_receipt_context() -> dict:
    school = SchoolSetting.objects.first()
    if not school:
        return {"name": "Tafiti School", "motto": "", "address": "", "phone": "", "email": ""}

    def clean(value):
        text = str(value or "").strip()
        return "" if text.lower() in {"none", "null", "-"} else text

    address = ", ".join(part for part in [clean(school.address), clean(school.city)] if part)
    return {
        "name": clean(school.school_name) or "Tafiti School",
        "motto": clean(school.school_motto),
        "address": address,
        "phone": clean(school.mobile) or clean(school.office_phone_number1),
        "email": clean(school.email),
    }


def _reconcile_overpayment_credit(bill: StudentBill) -> Decimal:
    """Keep only the genuinely unused portion of this bill's overpayment as student credit."""
    bill.refresh_from_db()
    applied_to_bill = bill.applied_credits.filter(amount__lt=0).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    credit_reduction = abs(Decimal(applied_to_bill))
    cash_due = max(Decimal(bill.net_amount_due) - credit_reduction, Decimal("0"))
    total_overpayment = max(Decimal(bill.amount_paid) - cash_due, Decimal("0"))

    used_from_this_overpayment = StudentCredit.objects.filter(
        student=bill.student,
        original_bill=bill,
        amount__lt=0,
        is_applied=True,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    remaining_overpayment = max(total_overpayment - abs(Decimal(used_from_this_overpayment)), Decimal("0"))

    unused = StudentCredit.objects.filter(
        student=bill.student,
        original_bill=bill,
        amount__gt=0,
        description__icontains="overpayment credit",
        is_applied=False,
    ).order_by("id")
    first = unused.first()
    if remaining_overpayment > 0:
        if first:
            first.amount = remaining_overpayment
            first.description = f"Overpayment credit from bill #{bill.id}"
            first.save(update_fields=["amount", "description"])
            unused.exclude(pk=first.pk).delete()
        else:
            StudentCredit.objects.create(
                student=bill.student,
                amount=remaining_overpayment,
                description=f"Overpayment credit from bill #{bill.id}",
                original_bill=bill,
                is_applied=False,
            )
    else:
        unused.delete()
    return remaining_overpayment
''',
)
replace(
    'backend/backend/student_finance.py',
    '        "credit": _money(max(-balance, Decimal("0")) + available_credit),',
    '        "credit": _money(available_credit),',
)
replace(
    'backend/backend/student_finance.py',
    '''                    "bill_id": bill.pk,
                },''',
    '''                    "bill_id": bill.pk,
                    "class": str(bill.academic_class.Class),
                    "term": str(bill.academic_class.term),
                    "balance_after": _money(max(Decimal(bill.balance), Decimal("0"))),
                    "credit_after": _money(bill.available_credits),
                    "recorded_by": payment.recorded_by,
                    "school": _school_receipt_context(),
                },''',
)

# 8) Print a clean official receipt with school and post-payment account details.
replace(
    'frontend/components/reference/ReferenceFeeAccountWorkspace.tsx',
    '''  student_number: string;
  bill_id: number;
}''',
    '''  student_number: string;
  bill_id: number;
  class: string;
  term: string;
  balance_after: string;
  credit_after: string;
  recorded_by: string;
  school: { name: string; motto: string; address: string; phone: string; email: string };
}''',
)
replace(
    'frontend/components/reference/ReferenceFeeAccountWorkspace.tsx',
    '''function statusClass(status: string) {
  if (status === 'Paid') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status === 'Partial') return 'border-amber-100 bg-amber-50 text-amber-700';
  if (status === 'Credit') return 'border-violet-100 bg-violet-50 text-violet-700';
  return 'border-rose-100 bg-rose-50 text-rose-700';
}
''',
    '''function statusClass(status: string) {
  if (status === 'Paid') return 'border-emerald-100 bg-emerald-50 text-emerald-700';
  if (status === 'Partial') return 'border-amber-100 bg-amber-50 text-amber-700';
  if (status === 'Credit') return 'border-violet-100 bg-violet-50 text-violet-700';
  return 'border-rose-100 bg-rose-50 text-rose-700';
}

function escapeHtml(value: string | number) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function printPaymentReceipt(receipt: ReceiptData) {
  const popup = window.open('', '_blank', 'width=760,height=920');
  if (!popup) return false;
  const contact = [receipt.school.address, receipt.school.phone, receipt.school.email].filter(Boolean).map(escapeHtml).join(' · ');
  popup.document.write(`<!doctype html>
<html><head><meta charset="utf-8"><title>Receipt ${escapeHtml(receipt.reference)}</title>
<style>
@page{size:A5 portrait;margin:10mm}*{box-sizing:border-box}body{font-family:Arial,sans-serif;color:#0f172a;margin:0;background:#fff}.receipt{border:1px solid #cbd5e1;padding:22px}.head{text-align:center;border-bottom:2px solid #0f3b82;padding-bottom:14px}.school{font-size:20px;font-weight:800;color:#0f3b82}.motto{font-size:10px;font-style:italic;margin-top:4px}.contact{font-size:9px;color:#64748b;margin-top:5px}.title{font-size:14px;font-weight:800;letter-spacing:.12em;margin-top:14px}.ref{font-size:10px;color:#475569;margin-top:4px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:18px}.field{border-bottom:1px solid #e2e8f0;padding:7px 0}.label{font-size:8px;font-weight:700;color:#64748b;text-transform:uppercase}.value{font-size:11px;font-weight:700;margin-top:3px}.amount{margin-top:18px;border:2px solid #0f3b82;padding:14px;text-align:center}.amount .value{font-size:24px;color:#0f3b82}.summary{margin-top:15px;font-size:10px;display:flex;justify-content:space-between;gap:12px}.signatures{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:38px;font-size:9px}.line{border-top:1px solid #64748b;padding-top:5px;text-align:center}.footer{text-align:center;font-size:8px;color:#64748b;margin-top:24px}
</style></head><body><div class="receipt"><div class="head"><div class="school">${escapeHtml(receipt.school.name)}</div>${receipt.school.motto ? `<div class="motto">${escapeHtml(receipt.school.motto)}</div>` : ''}${contact ? `<div class="contact">${contact}</div>` : ''}<div class="title">OFFICIAL PAYMENT RECEIPT</div><div class="ref">Receipt / Reference: ${escapeHtml(receipt.reference)}</div></div><div class="grid"><div class="field"><div class="label">Student</div><div class="value">${escapeHtml(receipt.student)}</div></div><div class="field"><div class="label">Student No.</div><div class="value">${escapeHtml(receipt.student_number)}</div></div><div class="field"><div class="label">Class</div><div class="value">${escapeHtml(receipt.class)}</div></div><div class="field"><div class="label">Term</div><div class="value">${escapeHtml(receipt.term)}</div></div><div class="field"><div class="label">Payment date</div><div class="value">${escapeHtml(receipt.date)}</div></div><div class="field"><div class="label">Payment method</div><div class="value">${escapeHtml(receipt.method)}</div></div><div class="field"><div class="label">Bill</div><div class="value">#${escapeHtml(receipt.bill_id)}</div></div><div class="field"><div class="label">Received by</div><div class="value">${escapeHtml(receipt.recorded_by)}</div></div></div><div class="amount"><div class="label">Amount received</div><div class="value">${escapeHtml(money(receipt.amount))}</div></div><div class="summary"><span>Balance after payment: <strong>${escapeHtml(money(receipt.balance_after))}</strong></span><span>Available credit: <strong>${escapeHtml(money(receipt.credit_after))}</strong></span></div><div class="signatures"><div class="line">Cashier / Bursar signature</div><div class="line">Parent / Payer signature</div></div><div class="footer">Computer-generated receipt · Keep this receipt for your records.</div></div></body></html>`);
  popup.document.close();
  popup.focus();
  window.setTimeout(() => { popup.print(); popup.close(); }, 250);
  return true;
}
''',
)
replace(
    'frontend/components/reference/ReferenceFeeAccountWorkspace.tsx',
    '>Tafiti School Management System</p><h2',
    '>{receipt.school.name}</p><h2',
)
replace(
    'frontend/components/reference/ReferenceFeeAccountWorkspace.tsx',
    '<button type="button" onClick={() => window.print()} className="clay-button-primary"><Printer size={14} />Print receipt</button>',
    '<button type="button" onClick={() => { if (!printPaymentReceipt(receipt)) toast.error(\'Printing blocked\', \'Allow pop-ups for this site, then try again.\'); }} className="clay-button-primary"><Printer size={14} />Print receipt</button>',
)

print('Requested patches applied successfully.')
