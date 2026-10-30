import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoriesPage } from '../pages/MemoriesPage';
import { db } from '../mocks/handlers';
import { renderPage } from './utils';

describe('MemoriesPage', () => {
  it('groups recordings by day and marks one as listened', async () => {
    const { user } = renderPage(<MemoriesPage />);
    expect(await screen.findByRole('heading', { name: 'Today' })).toBeInTheDocument();

    const before = db.recordings.filter((r) => !r.listened).length;
    const items = await screen.findAllByRole('listitem');
    const item = items.find((li) => within(li).queryByLabelText('Not listened yet'))!;
    expect(item).toBeDefined();
    await user.click(within(item).getByRole('button', { name: 'Mark listened' }));
    await waitFor(() => expect(within(item).queryByLabelText('Not listened yet')).not.toBeInTheDocument());
    expect(db.recordings.filter((r) => !r.listened)).toHaveLength(before - 1);
    expect(within(item).getByRole('button', { name: 'Mark unlistened' })).toBeInTheDocument();
  });

  it('marks a recording listened when playback starts', async () => {
    renderPage(<MemoriesPage />);
    const items = await screen.findAllByRole('listitem');
    const item = items.find((li) => within(li).queryByLabelText('Not listened yet'))!;
    fireEvent.play(within(item).getByLabelText(/Call with|Secret message|Voicemail/));
    await waitFor(() => expect(within(item).queryByLabelText('Not listened yet')).not.toBeInTheDocument());
  });

  it('filters by kind and contact', async () => {
    const { user } = renderPage(<MemoriesPage />);
    await screen.findAllByRole('listitem');
    await user.selectOptions(screen.getByLabelText('Kind'), 'secret');
    await waitFor(() => {
      const items = screen.getAllByRole('listitem');
      expect(items).toHaveLength(1);
      expect(items[0]).toHaveTextContent('Secret message');
    });
    await user.selectOptions(screen.getByLabelText('Kind'), '');
    await user.selectOptions(screen.getByLabelText('Who'), 'Grandpa');
    await waitFor(() => {
      for (const li of screen.getAllByRole('listitem')) expect(li).toHaveTextContent('Grandpa');
    });
  });

  it('shows the backup state and a download link', async () => {
    renderPage(<MemoriesPage />);
    const items = await screen.findAllByRole('listitem');
    expect(items.some((li) => li.textContent?.includes('backed up'))).toBe(true);
    const link = within(items[0]!).getByRole('link', { name: 'Download' });
    expect(link).toHaveAttribute('download');
  });
});
