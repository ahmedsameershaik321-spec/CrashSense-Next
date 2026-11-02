"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  clearVideoStreamSession,
  getCurrentUser,
  login,
  type CurrentUser,
} from "@/lib/api";
import type { AuthSession } from "@/lib/auth";

interface AuthContextValue {
  session: AuthSession | null;
  signIn: (email: string, password: string) => Promise<AuthSession>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);

  const signIn = useCallback(
    async (email: string, password: string): Promise<AuthSession> => {
      const tokenResponse = await login(email, password);
      const user: CurrentUser = await getCurrentUser(tokenResponse.access_token);
      const nextSession = {
        accessToken: tokenResponse.access_token,
        user,
        expiresInSeconds: tokenResponse.expires_in,
      };
      setSession(nextSession);
      return nextSession;
    },
    [],
  );

  const signOut = useCallback(() => {
    setSession(null);
    void clearVideoStreamSession().catch((error: unknown) => {
      console.error("Could not clear the protected video session.", error);
    });
  }, []);

  const value = useMemo(
    () => ({ session, signIn, signOut }),
    [session, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
