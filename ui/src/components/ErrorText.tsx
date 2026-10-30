import { errorMessage } from '../lib/errors';

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="error" role="alert">
      {errorMessage(error)}
    </div>
  );
}
