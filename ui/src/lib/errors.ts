import { ApiError } from '../api/client';

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'speed_dial_taken') return 'That speed dial digit is already taken. Pick another.';
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return 'Something went wrong.';
}
