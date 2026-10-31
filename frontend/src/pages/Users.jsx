import { useState } from 'react'
import { UserPlus } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, Field, PageHeader, Pill, Table } from '../components/ui'
import { titleCase } from '../utils/format'

export default function Users() {
  const toast = useToast()
  const u = useApi(api.users, [])
  const au = useApi(api.audit, [])
  const [f, setF] = useState({ user_id: '', role: 'faculty' })
  const [busy, setBusy] = useState(false)
  const assign = async (e) => { e.preventDefault(); setBusy(true); try { await api.assignRole(f.user_id.trim(), f.role); toast('Role assignment recorded', 'ok'); setF({ ...f, user_id: '' }); u.reload(); au.reload() } catch (x) { toast(x.message, 'error') } finally { setBusy(false) } }
  return (
    <>
      <PageHeader title="User Management" subtitle="Roles are enforced by the backend. Nobody can assign or change their own role." />
      <Async state={u} rows={2}>{(d) => (
        <div className="grid gap-5">
          <Card><Pill tone="warn" className="mb-3">{d.auth_mode === 'local' ? 'Local demo authentication' : 'Supabase authentication'}</Pill><p className="mb-3 text-sm text-muted">{d.note}</p>
            {d.accounts.length > 0 && <Table head={['Username', 'Name', 'Role', 'Department']}>{d.accounts.map((a) => <tr key={a.username}><td className="td font-bold text-navy">{a.username}</td><td className="td">{a.name}</td><td className="td"><Pill tone="lav">{titleCase(a.role)}</Pill></td><td className="td">{a.department || '-'}</td></tr>)}</Table>}</Card>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card as="form" onSubmit={assign} className="grid h-fit gap-3" aria-label="Assign role"><h2 className="text-lg font-extrabold text-navy">Record a role assignment</h2>
              <Field label="User ID" id="uid"><input id="uid" required className="field" value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} /></Field>
              <Field label="Role" id="role"><select id="role" className="field" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{['admin', 'faculty', 'department_coordinator', 'club_representative'].map((r) => <option key={r} value={r}>{titleCase(r)}</option>)}</select></Field>
              <Btn type="submit" variant="primary" loading={busy}><UserPlus className="h-4 w-4" />Assign</Btn></Card>
            <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Role assignments</h2>{d.role_assignments.length ? <Table head={['User', 'Role', 'Granted by']}>{d.role_assignments.map((r, i) => <tr key={i}><td className="td">{r.user_id}</td><td className="td">{titleCase(r.role)}</td><td className="td">{r.granted_by}</td></tr>)}</Table> : <Empty title="None recorded" />}</Card>
          </div>
          <Card><h2 className="mb-3 text-lg font-extrabold text-navy">Audit log (latest)</h2>
            <Async state={au} rows={1} emptyIf={(x) => !x.events.length} empty={<Empty title="No events yet" />}>{(x) => <Table head={['When', 'Actor', 'Action', 'Subject']}>{x.events.slice(0, 40).map((e) => <tr key={e.id}><td className="td whitespace-nowrap">{new Date(e.at).toLocaleString()}</td><td className="td">{e.actor}</td><td className="td"><Pill tone="info">{e.action}</Pill></td><td className="td">{e.subject}</td></tr>)}</Table>}</Async></Card>
        </div>)}</Async>
    </>
  )
}
