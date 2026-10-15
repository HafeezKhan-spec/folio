import { Route, Routes } from "react-router-dom";
import { AuthForm } from "./pages/AuthForm";
import { Billing } from "./pages/Billing";
import { Landing } from "./pages/Landing";
import { Studio } from "./pages/Studio";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<AuthForm mode="login" />} />
      <Route path="/signup" element={<AuthForm mode="signup" />} />
      <Route path="/app" element={<Studio />} />
      <Route path="/billing" element={<Billing />} />
      <Route path="*" element={<Landing />} />
    </Routes>
  );
}
