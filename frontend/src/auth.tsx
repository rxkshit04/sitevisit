import { createContext, type ReactNode, useContext, useEffect, useState } from 'react';
import { api, ensureCsrf } from './api';
import type { User } from './types';

interface AuthContext {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthContext>(null as unknown as AuthContext);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        await ensureCsrf();
        const me = await api<User>('/api/auth/me/');
        if (live) setUser(me);
      } catch {
        if (live) setUser(null);
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  async function login(username: string, password: string) {
    setUser(await api<User>('/api/auth/login/', { body: { username, password } }));
  }

  async function logout() {
    try {
      await api('/api/auth/logout/', { method: 'POST' });
    } catch {
      /* session may already be gone */
    }
    setUser(null);
  }

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}