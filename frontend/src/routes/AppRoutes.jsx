import { Navigate, Route, Routes } from "react-router-dom";

import { Splash } from "../components/ui/Splash";
import { useAuth } from "../hooks/useAuth";
import { AdminLayout } from "../layouts/AdminLayout";
import { DriverLayout } from "../layouts/DriverLayout";
import { Login } from "../pages/Login";
import { NotFound } from "../pages/NotFound";
import { Setup } from "../pages/Setup";
import { Bases } from "../pages/admin/Bases";
import { Customers } from "../pages/admin/Customers";
import { Dashboard } from "../pages/admin/Dashboard";
import { Deliveries } from "../pages/admin/Deliveries";
import { GeocodeQueue } from "../pages/admin/GeocodeQueue";
import { Security } from "../pages/admin/Security";
import { Planner } from "../pages/admin/Planner";
import { Routes as RoutesPage } from "../pages/admin/Routes";
import { Drivers } from "../pages/admin/Drivers";
import { Settings } from "../pages/admin/Settings";
import { Users } from "../pages/admin/Users";
import { Vehicles } from "../pages/admin/Vehicles";
import { DriverHome } from "../pages/driver/DriverHome";
import { DriverRoute } from "../pages/driver/DriverRoute";
import { ProtectedRoute } from "./ProtectedRoute";

/** Leva cada perfil para a sua area — a raiz nunca mostra tela de outro papel. */
function Inicio() {
  const { autenticado, carregando, usuario } = useAuth();
  if (carregando) return <Splash />;
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
        <Route path="entregas" element={<Deliveries />} />
        <Route path="planejamento" element={<Planner />} />
        <Route path="rotas" element={<RoutesPage />} />
        <Route path="enderecos" element={<GeocodeQueue />} />
        <Route path="clientes" element={<Customers />} />
        <Route path="motoristas" element={<Drivers />} />
        <Route path="veiculos" element={<Vehicles />} />
        <Route path="bases" element={<Bases />} />
        <Route path="usuarios" element={<Users />} />
        <Route path="seguranca" element={<Security />} />
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
        <Route path="rota/:id" element={<DriverRoute />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
