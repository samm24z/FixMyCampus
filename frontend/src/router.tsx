import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '@/components/layout/AppLayout';
import { HomePage } from '@/pages/HomePage';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { ResetPasswordPage } from '@/pages/ResetPasswordPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { TicketsPage } from '@/pages/TicketsPage';
import { TicketDetailPage } from '@/pages/TicketDetailPage';
import { AdminPage } from '@/pages/AdminPage';
import { StaffPage } from '@/pages/StaffPage';
import { AssistantPage } from '@/pages/AssistantPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { CreateComplaintPage } from '@/pages/CreateComplaintPage';
import { ProtectedRoute } from '@/lib/auth';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'reset-password', element: <ResetPasswordPage /> },
      { path: 'dashboard', element: <ProtectedRoute><DashboardPage /></ProtectedRoute> },
      { path: 'tickets', element: <ProtectedRoute><TicketsPage /></ProtectedRoute> },
      { path: 'tickets/new', element: <ProtectedRoute><CreateComplaintPage /></ProtectedRoute> },
      { path: 'tickets/:id', element: <ProtectedRoute><TicketDetailPage /></ProtectedRoute> },
      { path: 'admin', element: <ProtectedRoute roles={['ADMIN']}><AdminPage /></ProtectedRoute> },
      { path: 'staff', element: <ProtectedRoute roles={['STAFF', 'COORDINATOR', 'ADMIN']}><StaffPage /></ProtectedRoute> },
      { path: 'assistant', element: <ProtectedRoute><AssistantPage /></ProtectedRoute> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
