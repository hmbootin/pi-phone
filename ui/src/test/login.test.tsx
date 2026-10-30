import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Route, Routes } from 'react-router';
import { LoginPage } from '../pages/LoginPage';
import { db } from '../mocks/handlers';
import { renderPage } from './utils';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<div>home sweet home</div>} />
    </Routes>
  );
}

describe('LoginPage', () => {
  it('rejects a wrong password and accepts the right one', async () => {
    db.loggedIn = false;
    const { user } = renderPage(<App />, { route: '/login' });
    await user.type(screen.getByLabelText('Parent password'), 'nope');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/wrong password/i);

    await user.clear(screen.getByLabelText('Parent password'));
    await user.type(screen.getByLabelText('Parent password'), 'tincan');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('home sweet home')).toBeInTheDocument();
    expect(db.loggedIn).toBe(true);
  });
});
