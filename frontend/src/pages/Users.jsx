import { useState } from 'react'
import { Check, UserPlus, X } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, Field, PageHeader, Pill, Table, statusTone } from '../components/ui'
import { titleCase } from '../utils/format'

export default function Users() {
  const toast = useToast()
  const u = useApi(api.users, [])
  const au = useApi(api.audit, [])
  const [f, setF] = useState({ user_id: '', role: 'faculty' })
  const [busy, setBusy] = useState('')
  const decide = async (email, action, role) => { setBusy(email); try { await api.decideAccount(email, action, role); toast(action === 'approve' ? 'Account approved' : 'Request declined', 'ok'); u.reload(); au.reload() } catch (x) { toast(x.message, 'error') } finally { setBusy('') } }
  const assign = async (e) => { e.preventDefault(); try { await api.assignRole(f.user_id.trim(), f.role); toast('Role assignment recorded', 'ok'); setF({ ...f, user_id: '' }); u.reload() } catch (x) { toast(x.message, 'error') } }
  return (
    <>
      <PageHeader title="Users" subtitle="Review access requests and see who can sign in. Nobody can change their own role." />
      <Async state={u} rows={2}>{(d) => {
        const pending = d.accounts.filter((a) => a.status === 'pending')
        return (
          <div className="grid gap-6">
            <Card><h2 className="mb-3 text-lg font-bold text-navy">Access requests {pending.length > 0 && <Pill tone="warn">{pending.length} waiting</Pill>}</h2>
              {pending.length === 0 ? <Empty title="No requests waiting" /> : <Table head={['Name', 'Email', 'Requested role', 'Department', '']}>{pending.map((a) => (
                <tr key={a.email}><td className="td font-semibold text-navy">{a.name}</td><td className="td">{a.email}</td><td className="td"><Pill tone="lav">{titleCase(a.requested_role || a.role)}</Pill></td><td className="td">{a.department || '-'}</td>
                  <td className="td"><div className="flex gap-2"><Btn variant="mint" loading={busy === a.email} onClick={() => decide(a.email, 'approve')}><Check className="h-4 w-4" />Approve</Btn><Btn onClick={() => decide(a.email, 'reject')}><X className="h-4 w-4" />Decline</Btn></div></td></tr>))}</Table>}</Card>
            <Card><h2 className="mb-3 text-lg font-bold text-navy">All accounts</h2>
              <Table head={['Name', 'Email', 'Role', 'Status']}>{d.accounts.map((a) => <tr key={a.email}><td className="td font-semibold text-navy">{a.name}</td><td className="td">{a.email}</td><td className="td">{titleCase(a.role)}</td><td className="td"><Pill tone={a.status === 'active' ? 'ok' : statusTone(a.status)}>{titleCase(a.status)}</Pill></td></tr>)}</Table></Card>
            <div className="grid gap-6 lg:grid-cols-2">
              <Card as="form" onSubmit={assign} className="grid h-fit gap-3" aria-label="Record role assignment"><h2 className="text-lg font-bold text-navy">Record a role assignment</h2>
                <Field label="User ID" id="uid"><input id="uid" required className="field" value={f.user_id} onChange={(e) => setF({ ...f, user_id: e.target.value })} /></Field>
                <Field label="Role" id="role"><select id="role" className="field" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{['faculty', 'department_coordinator', 'club_representative'].map((r) => <option key={r} value={r}>{titleCase(r)}</option>)}</select></Field>
                <Btn type="submit" variant="primary"><UserPlus className="h-4 w-4" />Record</Btn></Card>
              <Card><h2 className="mb-3 text-lg font-bold text-navy">Recent activity</h2>
                <Async state={au} rows={1} emptyIf={(x) => !x.events.length} empty={<Empty title="No activity yet" />}>{(x) => <Table head={['When', 'Who', 'Action']}>{x.events.slice(0, 12).map((e) => <tr key={e.id}><td className="td whitespace-nowrap">{new Date(e.at).toLocaleString()}</td><td className="td">{e.actor}</td><td className="td"><Pill tone="info">{e.action}</Pill></td></tr>)}</Table>}</Async></Card>
            </div>
          </div>)
      }}</Async>
    </>
  )
}
