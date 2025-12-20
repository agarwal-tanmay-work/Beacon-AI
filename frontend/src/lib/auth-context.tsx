"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

interface AdminContextType {
    token: string | null;
    login: (token: string) => void;
    logout: () => void;
    isAuthenticated: boolean;
}

const AdminContext = createContext<AdminContextType>({
    token: null,
    login: () => { },
    logout: () => { },
    isAuthenticated: false,
});

export function AdminProvider({ children }: { children: React.ReactNode }) {
    const [token, setToken] = useState<string | null>(() => {
        if (typeof window !== "undefined") {
            return localStorage.getItem("admin_token");
        }
        return null;
    });
    const router = useRouter();

    useEffect(() => {
        if (token) {
            api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
        }
    }, [token]);

    const login = (newToken: string) => {
        localStorage.setItem("admin_token", newToken);
        setToken(newToken);
        api.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
        router.push("/dashboard");
    };

    const logout = () => {
        localStorage.removeItem("admin_token");
        setToken(null);
        delete api.defaults.headers.common["Authorization"];
        router.push("/login");
    };

    return (
        <AdminContext.Provider value={{ token, login, logout, isAuthenticated: !!token }}>
            {children}
        </AdminContext.Provider>
    );
}

export const useAdminAuth = () => useContext(AdminContext);
