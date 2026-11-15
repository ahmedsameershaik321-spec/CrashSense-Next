"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  BellRing,
  CheckCircle2,
  LoaderCircle,
  ShieldAlert,
} from "lucide-react";
import {
  ApiError,
  createEmergencyAlertAudit,
  listEmergencyAlertAudit,
  type EmergencyAlertAudit,
} from "@/lib/api";

interface AlertAuditPanelProps {
  accessToken: string;
  analysisId: string;
  candidateId: string;
}

function messageForError(reason: unknown): string {
  if (reason instanceof ApiError) {
    if (reason.status === 401) {
      return "Your session expired. Sign in again to view alert audit records.";
    }
    if (reason.status === 403) {
      return "Your account is not authorized to view alert audit records.";
    }
    return reason.message;
  }
  return "Alert audit records could not be loaded. Try again.";
}

export function AlertAuditPanel({
  accessToken,
  analysisId,
  candidateId,
}: AlertAuditPanelProps) {
  const [records, setRecords] = useState<EmergencyAlertAudit[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [error, setError] = useState("");

  const loadRecords = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRecords(
        await listEmergencyAlertAudit(accessToken, analysisId, candidateId),
      );
    } catch (reason) {
      setError(messageForError(reason));
    } finally {
      setLoading(false);
    }
  }, [accessToken, analysisId, candidateId]);

  useEffect(() => {
    let active = true;
    void listEmergencyAlertAudit(accessToken, analysisId, candidateId)
      .then((response) => {
        if (active) {
          setRecords(response);
          setError("");
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(messageForError(reason));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [accessToken, analysisId, candidateId]);

  const recordAuditOnlyAction = async () => {
    setSaving(true);
    setError("");
    try {
      await createEmergencyAlertAudit(accessToken, analysisId, candidateId);
      setAcknowledged(false);
      await loadRecords();
    } catch (reason) {
      setError(messageForError(reason));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-labelledby="alert-audit-title"
      className="rounded-xl border border-line bg-panel p-4 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-amber-200 bg-amber-50 text-amber-800">
          <BellRing aria-hidden="true" className="h-4 w-4" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-slate-900" id="alert-audit-title">
            Notification audit
          </h2>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Audit-only mode. CrashSense does not send an alert or contact an
            emergency service.
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
        <p className="flex items-start gap-2 text-xs leading-5 text-amber-800">
          <ShieldAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
          Recording an audit entry only records that an operator reviewed this
          candidate. Delivery status will remain “Not sent”.
        </p>
        <label className="mt-3 flex items-start gap-2 text-xs text-slate-600">
          <input
            checked={acknowledged}
            className="mt-0.5 accent-sky-400"
            onChange={(event) => setAcknowledged(event.target.checked)}
            type="checkbox"
          />
          I understand this action will not send or deliver a notification.
        </label>
        <button
          className="mt-3 rounded-lg border border-amber-200 px-3 py-2 text-xs font-medium text-amber-800 hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-40"
          disabled={!acknowledged || saving}
          onClick={() => void recordAuditOnlyAction()}
          type="button"
        >
          {saving ? "Recording audit…" : "Record review (not sent)"}
        </button>
      </div>

      {error && (
        <div className="mt-3 flex items-center justify-between gap-3 text-xs text-rose-700" role="alert">
          <span className="flex items-center gap-2">
            <AlertCircle aria-hidden="true" className="h-4 w-4 shrink-0" />
            {error}
          </span>
          <button
            className="shrink-0 rounded-md border border-line px-2.5 py-1.5 text-[10px] text-slate-700"
            onClick={() => void loadRecords()}
            type="button"
          >
            Retry notification audit
          </button>
        </div>
      )}

      <div aria-live="polite" className="mt-4 space-y-2">
        {loading ? (
          <p className="flex items-center gap-2 text-xs text-slate-600" role="status">
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
            Loading notification audit history…
          </p>
        ) : records.length === 0 ? (
          <p className="text-xs text-slate-500">No audit entries for this candidate.</p>
        ) : (
          records.map((record) => (
            <article
              className="rounded-lg border border-line bg-slate-50 p-3"
              key={record.id}
            >
              <p className="flex items-center gap-2 text-xs font-semibold text-slate-900">
                <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-amber-800" />
                Not sent
              </p>
              <p className="mt-1 text-[11px] leading-5 text-slate-600">
                {record.delivery_result}
              </p>
              <time
                className="mt-2 block text-[10px] text-slate-500"
                dateTime={record.created_at}
              >
                Audit record: {new Date(record.created_at).toLocaleString()}
              </time>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
