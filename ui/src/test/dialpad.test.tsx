import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DialPadPage } from '../pages/DialPadPage';
import { db } from '../mocks/handlers';
import { renderPage } from './utils';

describe('DialPadPage', () => {
  it('shows contacts and features on the digits', async () => {
    renderPage(<DialPadPage />);
    expect(await screen.findByRole('listitem', { name: 'Digit 2: Grandma' })).toBeInTheDocument();
    expect(screen.getByRole('listitem', { name: 'Digit 7: Fun fact: dinosaurs' })).toBeInTheDocument();
    expect(screen.getByRole('listitem', { name: 'Digit 0: Nothing' })).toBeInTheDocument();
  });

  it('edits a feature, saves it, and previews the prompt', async () => {
    const { user } = renderPage(<DialPadPage />);
    await user.click(await screen.findByRole('listitem', { name: 'Digit 7: Fun fact: dinosaurs' }));
    const sheet = screen.getByRole('region', { name: 'Digit 7 settings' });
    const topic = within(sheet).getByLabelText('Topic');
    await user.clear(topic);
    await user.type(topic, 'space');
    await user.click(within(sheet).getByRole('button', { name: 'Save' }));
    expect(await within(sheet).findByText('Saved.')).toBeInTheDocument();
    expect(db.features.find((f) => f.digit === 7)!.config.topic).toBe('space');
    expect(await screen.findByRole('listitem', { name: 'Digit 7: Fun fact: space' })).toBeInTheDocument();

    await user.click(within(sheet).getByRole('button', { name: 'Preview' }));
    expect(await within(sheet).findByText(/fun fact about space/i)).toBeInTheDocument();
    const audio = within(sheet).getByLabelText('Preview of digit 7');
    expect(audio).toHaveAttribute('src', '/api/audio/prompts/preview-7.wav');
  });

  it('changes a digit to a different kind with its own config', async () => {
    const { user } = renderPage(<DialPadPage />);
    await user.click(await screen.findByRole('listitem', { name: 'Digit 0: Nothing' }));
    const sheet = screen.getByRole('region', { name: 'Digit 0 settings' });
    await user.selectOptions(within(sheet).getByLabelText('What happens'), 'secret_message');
    await user.type(within(sheet).getByLabelText('For'), 'Dad');
    await user.selectOptions(within(sheet).getByLabelText('Notify via'), 'email');
    await user.click(within(sheet).getByRole('button', { name: 'Save' }));
    await within(sheet).findByText('Saved.');
    expect(db.features.find((f) => f.digit === 0)).toMatchObject({
      kind: 'secret_message',
      config: { recipient: 'Dad', notify: 'email' },
      enabled: true,
    });
    expect(await screen.findByRole('listitem', { name: 'Digit 0: Secret for Dad' })).toBeInTheDocument();
  });

  it('does not open an editor for a contact digit', async () => {
    const { user } = renderPage(<DialPadPage />);
    await user.click(await screen.findByRole('listitem', { name: 'Digit 2: Grandma' }));
    expect(screen.queryByRole('region', { name: /settings/ })).not.toBeInTheDocument();
  });
});
