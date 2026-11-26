import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SettingsPage } from '../pages/SettingsPage';
import { db } from '../mocks/handlers';
import { renderPage } from './utils';

async function ringtoneList() {
  const list = await screen.findByRole('list', { name: 'Ringtones' });
  await within(list).findByText('Classic');
  return list;
}

describe('Ringtone settings', () => {
  it('lists built-in and uploaded ringtones with a preview each', async () => {
    renderPage(<SettingsPage />);
    const list = await ringtoneList();
    const items = within(list).getAllByRole('listitem');
    expect(items.map((li) => within(li).getByRole('radio').getAttribute('value'))).toEqual([
      'classic',
      'chime',
      'birds',
      'grandmas-doorbell',
    ]);
    expect(within(list).getByRole('radio', { name: /Classic/ })).toBeChecked();
    expect(within(list).getByLabelText('Preview of Chime')).toHaveAttribute('src', '/api/ringtones/chime/audio');
    expect(items[0]).toHaveTextContent('built in');
    expect(items[3]).toHaveTextContent('uploaded');
    // Only uploads can be deleted.
    expect(within(list).queryByRole('button', { name: 'Delete Classic' })).not.toBeInTheDocument();
    expect(within(list).getByRole('button', { name: 'Delete Grandmas doorbell' })).toBeInTheDocument();
  });

  it('picks a ringtone and volume and saves them with the settings', async () => {
    const { user } = renderPage(<SettingsPage />);
    const list = await ringtoneList();
    await user.click(within(list).getByRole('radio', { name: /Birds/ }));
    expect(within(list).getByRole('radio', { name: /Birds/ })).toBeChecked();
    const slider = screen.getByLabelText(/Ringer volume/);
    expect(slider).toHaveValue('80');
    // Range inputs do not take typing; fire the change a drag would.
    fireEvent.change(slider, { target: { value: '35' } });
    expect(screen.getByLabelText(/Ringer volume/)).toHaveValue('35');
    expect(screen.getByText('Ringer volume (35%)')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    expect(await screen.findByText('Settings saved.')).toBeInTheDocument();
    expect(db.settings.ringtone).toBe('birds');
    expect(db.settings.ringer_volume).toBe(35);
  });

  it('uploads a ringtone and selects it', async () => {
    const { user } = renderPage(<SettingsPage />);
    await ringtoneList();
    const file = new File([new Uint8Array(64_000)], 'Our Jingle.wav', { type: 'audio/wav' });
    await user.upload(screen.getByLabelText('Upload a ringtone'), file);
    const list = await ringtoneList();
    const radio = await within(list).findByRole('radio', { name: /Our jingle/ });
    expect(radio).toBeChecked();
    expect(db.ringtones.find((r) => r.name === 'our-jingle')).toMatchObject({ builtin: false, duration_seconds: 2 });

    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await screen.findByText('Settings saved.');
    expect(db.settings.ringtone).toBe('our-jingle');
  });

  it('shows the backend error when an upload is rejected', async () => {
    const { user } = renderPage(<SettingsPage />);
    await ringtoneList();
    const file = new File([new Uint8Array(10)], 'chime.wav', { type: 'audio/wav' });
    await user.upload(screen.getByLabelText('Upload a ringtone'), file);
    expect(await screen.findByRole('alert')).toHaveTextContent(/built-in ringtone/);
  });

  it('deleting the chosen upload falls back to classic', async () => {
    const { user } = renderPage(<SettingsPage />);
    let list = await ringtoneList();
    await user.click(within(list).getByRole('radio', { name: /Grandmas doorbell/ }));
    await user.click(screen.getByRole('button', { name: 'Save settings' }));
    await screen.findByText('Settings saved.');
    expect(db.settings.ringtone).toBe('grandmas-doorbell');

    await user.click(within(list).getByRole('button', { name: 'Delete Grandmas doorbell' }));
    await waitFor(() => expect(within(list).queryByText('Grandmas doorbell')).not.toBeInTheDocument());
    list = await ringtoneList();
    expect(within(list).getByRole('radio', { name: /Classic/ })).toBeChecked();
    expect(db.settings.ringtone).toBe('classic');
    expect(db.ringtones.some((r) => r.name === 'grandmas-doorbell')).toBe(false);
  });
});
