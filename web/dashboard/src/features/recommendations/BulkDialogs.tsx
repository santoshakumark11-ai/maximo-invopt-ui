/**
 * BulkApproveDialog / BulkRejectDialog
 *
 * Both accept a nullable recIds prop — open when truthy, closed when null.
 * Uses react-hook-form built-in validation (no @hookform/resolvers needed).
 */
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Modal, TextArea, InlineNotification, InlineLoading } from '@carbon/react';
import { useBulkApprove, useBulkReject } from '@/api/mutations';

// ─── Bulk Approve ─────────────────────────────────────────────────────────────

interface BulkApproveProps {
  recIds: string[] | null;
  onClose: () => void;
}

interface ApproveForm {
  justification: string;
}

export function BulkApproveDialog({ recIds, onClose }: BulkApproveProps) {
  const { mutate, isPending, isError, error, reset: resetMutation } = useBulkApprove();

  const { register, handleSubmit, reset } = useForm<ApproveForm>({
    defaultValues: { justification: '' },
  });

  useEffect(() => {
    if (recIds) {
      reset({ justification: '' });
      resetMutation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recIds?.join(',')]);

  function onSubmit(values: ApproveForm) {
    if (!recIds?.length) return;
    mutate(
      { recIds, ...(values.justification ? { justification: values.justification } : {}) },
      { onSuccess: onClose }
    );
  }

  const count = recIds?.length ?? 0;

  return (
    <Modal
      open={Boolean(recIds?.length)}
      modalHeading={`Approve ${count} Recommendation${count !== 1 ? 's' : ''}`}
      primaryButtonText={isPending ? 'Approving…' : 'Approve'}
      secondaryButtonText="Cancel"
      onRequestClose={onClose}
      onRequestSubmit={handleSubmit(onSubmit)}
      primaryButtonDisabled={isPending}
    >
      {isError && (
        <InlineNotification
          kind="error"
          title="Failed to approve"
          subtitle={(error as Error)?.message}
          lowContrast
          style={{ marginBottom: '1rem' }}
        />
      )}

      <TextArea
        id="bulk-approve-justification"
        labelText="Justification (optional)"
        helperText="Optionally explain why these recommendations are being approved"
        placeholder="Add a note for the audit trail…"
        rows={3}
        {...register('justification')}
      />

      {isPending && <InlineLoading description="Approving…" style={{ marginTop: '1rem' }} />}
    </Modal>
  );
}

// ─── Bulk Reject ──────────────────────────────────────────────────────────────

interface BulkRejectProps {
  recIds: string[] | null;
  onClose: () => void;
}

interface RejectForm {
  reason: string;
}

export function BulkRejectDialog({ recIds, onClose }: BulkRejectProps) {
  const { mutate, isPending, isError, error, reset: resetMutation } = useBulkReject();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RejectForm>({ defaultValues: { reason: '' } });

  useEffect(() => {
    if (recIds) {
      reset({ reason: '' });
      resetMutation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recIds?.join(',')]);

  function onSubmit(values: RejectForm) {
    if (!recIds?.length) return;
    mutate({ recIds, reason: values.reason }, { onSuccess: onClose });
  }

  const count = recIds?.length ?? 0;

  return (
    <Modal
      open={Boolean(recIds?.length)}
      modalHeading={`Reject ${count} Recommendation${count !== 1 ? 's' : ''}`}
      primaryButtonText={isPending ? 'Rejecting…' : 'Reject'}
      secondaryButtonText="Cancel"
      onRequestClose={onClose}
      onRequestSubmit={handleSubmit(onSubmit)}
      primaryButtonDisabled={isPending}
      danger
    >
      {isError && (
        <InlineNotification
          kind="error"
          title="Failed to reject"
          subtitle={(error as Error)?.message}
          lowContrast
          style={{ marginBottom: '1rem' }}
        />
      )}

      <TextArea
        id="bulk-reject-reason"
        labelText="Reason for rejection"
        helperText="Minimum 10 characters"
        placeholder="Describe why these recommendations are being rejected…"
        rows={4}
        invalid={Boolean(errors.reason)}
        invalidText={errors.reason?.message}
        {...register('reason', {
          required: 'Reason is required',
          minLength: { value: 10, message: 'Reason must be at least 10 characters' },
        })}
      />

      {isPending && <InlineLoading description="Rejecting…" style={{ marginTop: '1rem' }} />}
    </Modal>
  );
}
