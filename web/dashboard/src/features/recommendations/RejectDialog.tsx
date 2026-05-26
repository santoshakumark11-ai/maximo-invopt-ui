/**
 * RejectDialog — modal to reject a single recommendation with a required reason field.
 * Uses Carbon Modal + react-hook-form (built-in validation, no resolver dependency).
 */
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Modal, TextArea, InlineNotification, InlineLoading } from '@carbon/react';
import { useRejectRec } from '@/api/mutations';

interface FormValues {
  reason: string;
}

interface Props {
  recId: string | null;
  onClose: () => void;
}

export function RejectDialog({ recId, onClose }: Props) {
  const { mutate, isPending, isError, error, reset: resetMutation } = useRejectRec();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ defaultValues: { reason: '' } });

  useEffect(() => {
    if (recId) {
      reset({ reason: '' });
      resetMutation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recId]);

  function onSubmit(values: FormValues) {
    if (!recId) return;
    mutate({ recId, payload: { reason: values.reason } }, { onSuccess: onClose });
  }

  return (
    <Modal
      open={Boolean(recId)}
      modalHeading="Reject Recommendation"
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
        id="reject-reason"
        labelText="Reason for rejection"
        helperText="Minimum 10 characters"
        placeholder="Describe why this recommendation is being rejected…"
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
