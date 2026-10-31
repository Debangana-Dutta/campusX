import { Navigate, useLocation } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useAuth } from '../contexts/AppContexts'
import { Empty, LoadingBlock } from '../components/ui'

/** Redirects unauthenticated users to /login; shows an Unauthorised page when the role is not allowed.
 *  (Convenience only - the backend independently enforces every permission.) */
export default function Guard({ roles, children }) {
  const { user, loading } = useAuth()
  const loc = useLocation()
  if (loading) return <div className="p-8"><LoadingBlock /></div>
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />
  if (roles && !roles.includes(user.role)) {
    return <Empty icon={ShieldAlert} title="You don't have access to this page" hint={`Your role (${user.role.replace(/_/g, ' ')}) cannot open it. Use the menu to go to a page you can use.`} />
  }
  return children
}
