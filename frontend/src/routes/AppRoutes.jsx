import { Navigate, Route, Routes } from "react-router-dom";

import { AdminLayout } from "../layouts/AdminLayout";
import { DriverLayout } from "../layouts/DriverLayout";
import { Dashboard } from "../pages/admin/Dashboard";
import { Settings } from "../pages/admin/Settings";
import { Users } from "../pages/admin/Users";
import { DriverHome } from "../pages/driver/DriverHome";
import { Login } from "../pages/Login";
import { NotFound } from "../pages/NotFound";
import { Setup } from "../pages/Setup";
import { useAuth } from "../hooks/useAuth";
import { ProtectedRoute } from "./ProtectedRoute";

/** Leva cada perfil para a sua area — a raiz nunca mostra tela de outro papel. */
function Inicio() {
  const { autenticado, carregando, usuario } = useAuth();
  if (carregando) return <div className="carregando-tela">Carregando...</div>;
  if (!autenticado) return <Navigate to="/entrar" replace />;
  return <Navigate to={usuario.role === "ADMIN" ? "/admin" : "/motorista"} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Inicio />} />
      <Route path="/entrar" element={<Login />} />
      <Route path="/primeiro-acesso" element={<Setup />} />

      <Route
        path="/admin"
        element={
          <ProtectedRoute papel="ADMIN">
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="usuarios" element={<Users />} />
        <Route path="configuracoes" element={<Settings />} />
      </Route>

      <Route
        path="/motorista"
        element={
          <ProtectedRoute papel="MOTORISTA">
            <DriverLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DriverHome />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
