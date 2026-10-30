import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ContactsPage } from '../pages/ContactsPage';
import { db } from '../mocks/handlers';
import { renderPage } from './utils';

describe('ContactsPage', () => {
  it('lists contacts with speed dial badges', async () => {
    renderPage(<ContactsPage />);
    const grandma = await screen.findByRole('article', { name: 'Grandma' });
    expect(within(grandma).getByLabelText('Speed dial 2')).toHaveTextContent('2');
    expect(screen.getByRole('article', { name: 'Auntie May' })).toHaveTextContent(/do not disturb/i);
  });

  it('shows a friendly error when the speed dial is taken, then succeeds on a free digit', async () => {
    const { user } = renderPage(<ContactsPage />);
    await screen.findByRole('article', { name: 'Grandma' });
    await user.click(screen.getByRole('button', { name: 'Add contact' }));

    const form = screen.getByRole('form', { name: 'New contact' });
    await user.type(within(form).getByLabelText('Name'), 'Uncle Bob');
    await user.type(within(form).getByLabelText('Phone number'), '+15555550199');

    // Digits used by other contacts are disabled in the picker.
    expect(within(form).getByRole('radio', { name: /Digit 2, Grandma/ })).toBeDisabled();

    // Simulate a race: pick a free digit, then another parent takes it before we save.
    await user.click(within(form).getByRole('radio', { name: /Digit 7/ }));
    db.contacts.push({ ...db.contacts[0]!, id: 999, name: 'Racer', speed_dial: 7 });
    await user.click(within(form).getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/already taken/i);

    // Form is still open; pick another digit and save.
    db.contacts = db.contacts.filter((c) => c.id !== 999);
    await user.click(within(form).getByRole('radio', { name: /Digit 1/ }));
    await user.click(within(form).getByRole('button', { name: 'Save' }));

    const bob = await screen.findByRole('article', { name: 'Uncle Bob' });
    expect(within(bob).getByLabelText('Speed dial 1')).toHaveTextContent('1');
    expect(screen.queryByRole('form', { name: 'New contact' })).not.toBeInTheDocument();
  });

  it('toggles enabled and edits a contact', async () => {
    const { user } = renderPage(<ContactsPage />);
    const grandma = await screen.findByRole('article', { name: 'Grandma' });
    await user.click(within(grandma).getByRole('switch', { name: 'Enable Grandma' }));
    await waitFor(() => expect(db.contacts[0]!.enabled).toBe(false));

    await user.click(within(grandma).getByRole('button', { name: 'Edit' }));
    const form = screen.getByRole('form', { name: 'Edit contact' });
    const max = within(form).getByLabelText('Max minutes per call');
    await user.clear(max);
    await user.type(max, '7');
    await user.click(within(form).getByRole('button', { name: 'Save' }));
    const updated = await screen.findByRole('article', { name: 'Grandma' });
    expect(updated).toHaveTextContent('7 min max');
  });

  it('deletes a contact after confirmation', async () => {
    const { user } = renderPage(<ContactsPage />);
    const dad = await screen.findByRole('article', { name: 'Dad at work' });
    await user.click(within(dad).getByRole('button', { name: 'Delete' }));
    await user.click(within(dad).getByRole('button', { name: 'Really delete' }));
    await waitFor(() => expect(screen.queryByRole('article', { name: 'Dad at work' })).not.toBeInTheDocument());
  });
});

describe('ContactsPage memory keys', () => {
  it('shows the memory key on the badge and offers free keys in the form', async () => {
    const { user } = renderPage(<ContactsPage />);
    const grandma = await screen.findByRole('article', { name: 'Grandma' });
    expect(within(grandma).getByLabelText('Speed dial 2')).toHaveAttribute('title', 'Also on M1');

    await user.click(screen.getByRole('button', { name: 'Add contact' }));
    const form = screen.getByRole('form', { name: 'New contact' });
    await user.type(within(form).getByLabelText('Name'), 'Mom');
    await user.type(within(form).getByLabelText('Phone number'), '+15555550101');
    // Save needs a digit or a key.
    expect(within(form).getByRole('button', { name: 'Save' })).toBeDisabled();
    const select = within(form).getByLabelText('Memory key');
    expect(within(select).getByRole('option', { name: /M1/ })).toBeDisabled();
    await user.selectOptions(select, 'sos');
    await user.click(within(form).getByRole('button', { name: 'Save' }));

    const mom = await screen.findByRole('article', { name: 'Mom' });
    expect(within(mom).getByLabelText('Key SOS')).toHaveTextContent('SOS');
    expect(db.contacts.find((c) => c.name === 'Mom')).toMatchObject({ speed_dial: null, memory_key: 'sos' });
  });
});
