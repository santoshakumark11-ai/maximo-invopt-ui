/**
 * EditValueDialog — planner edits the recommended value with justification.
 * Handles 409 version-conflict gracefully.
 *
 * Carbon NumberInput has a non-standard onChange signature, so we use
 * useState for the number field and react-hook-form only for the text area.
 */
import { useEffect, useState, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { Modal, NumberInput, TextArea, InlineNotification, InlineLoading } from '@carbon/react';
import { useEditRec } from '@/api/mutations';
import type { RecDetail } from '@/types';
import { HttpError } from '@/api/client';

interface FormValues {
  justification: string;
}

interface Props {
  rec: RecDetail | null;
  onClose: () => void;
}

export function EditValueDialog({ rec, onClose }: Props) {
  const { mutate, isPending, isError, error, reset: resetMutation } = useEditRec();

  // Initialise from rec — the parent passes key={rec.recId} so this component
  // remounts whenever the target recommendation changes, giving us fresh state
  // without needing setState inside an effect.
  const initialValue = rec
    ? typeof rec.recommendedValue === 'number'
      ? rec.recommendedValue
      : 0
    : 0;

  const [recValue, setRecValue] = useState<number>(initialValue);
  const [recValueError, setRecValueError] = useState<string>('');

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({
    defaultValues: { justification: '' },
  });

  // Reset external library state (mutation + form) when the dialog opens.
  // We intentionally do NOT call React setState here — initial state is
  // derived from rec above; key-based remounting handles subsequent opens.
  const didMount = useRef(false);
  useEffect(() => {
    if (!didMount.current) {
      didMount.current = true;
      return;
    }
    reset({ justification: '' });
    resetMutation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rec?.recId]);

  function onSubmit(values: FormValues) {
    if (!rec) return;

    if (recValue < 0 || isNaN(recValue)) {
      setRecValueError('Value must be 0 or more');
      return;
    }
    setRecValueError('');

    mutate(
      {
        recId: rec.recId,
        payload: {
          recommendedValue: recValue,
          justification: values.justification,
          expectedVersion: rec.version,
        },
      },
      { onSuccess: onClose }
    );
  }

  const conflictError = isError && error instanceof HttpError && error.status === 409;

  return (
    <Modal
      open={Boolean(rec)}
      modalHeading="Edit Recommended Value"
      primaryButtonText={isPending ? 'Saving...' : 'Save'}
      secondaryButtonText="Cancel"
      onRequestClose={onClose}
      onRequestSubmit={handleSubmit(onSubmit)}
      primaryButtonDisabled={isPending}
    >
      {conflictError && (
        <InlineNotification
          kind="warning"
          title="Version conflict"
          subtitle="This recommendation was edited by someone else. Please close and reload."
          lowContrast
          style={{ marginBottom: '1rem' }}
        />
      )}
      {isError && !conflictError && (
        <InlineNotification
          kind="error"
          title="Failed to save"
          subtitle={(error as Error)?.message}
          lowContrast
          style={{ marginBottom: '1rem' }}
        />
      )}

      <NumberInput
        id="edit-recommended-value"
        label="Recommended value"
        helperText="Enter the updated recommended quantity or level"
        min={0}
        step={1}
        value={recValue}
        invalid={Boolean(recValueError)}
        invalidText={recValueError}
        onChange={(_e: React.MouseEvent, state: { value: string | number }) => {
          setRecValue(Number(state.value));
        }}
      />

      <TextArea
        id="edit-justification"
        labelText="Justification"
        helperText="Minimum 50 characters — explain the reason for this change"
        placeholder="Describe why the recommended value is being changed..."
        rows={4}
        style={{ marginTop: '1rem' }}
        invalid={Boolean(errors.justification)}
        invalidText={errors.justification?.message}
        {...register('justification', {
          required: 'Justification is required',
          minLength: { value: 50, message: 'Justification must be at least 50 characters' },
        })}
      />

      {isPending && <InlineLoading description="Saving..." style={{ marginTop: '1rem' }} />}
    </Modal>
  );
}
