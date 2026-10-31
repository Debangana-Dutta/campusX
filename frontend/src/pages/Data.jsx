import { useRef, useState } from 'react'
import { Download, Pencil, Plus, Trash2, Upload } from 'lucide-react'
import { api } from '../services/api'
import { useApi } from '../hooks/useApi'
import { useToast } from '../contexts/AppContexts'
import { Async, Btn, Card, Empty, Modal, PageHeader, Table, Tabs } from '../components/ui'
import { download } from '../utils/format'

const ENT = { rooms: ['id', 'type', 'capacity', 'accessible'], faculty: ['id', 'name', 'department', 'max_hours_per_day'], groups: ['id', 'year', 'size'], courses: ['id', 'title', 'department'], sessions: ['id', 'course_id', 'kind', 'faculty_id', 'duration', 'size'] }
const TEMPLATE = { rooms: { id: '', name: '', building: '', type: 'classroom', capacity: 40, features: [], accessible: false, allowed_uses: ['lecture', 'tutorial', 'event'] } }

export default function Data() {
  const toast = useToast()
  const [ent, setEnt] = useState('rooms')
  const list = useApi(() => api.dataList(ent), [ent])
  const [edit, setEdit] = useState(null)    // { id|null, text }
  const [del, setDel] = useState(null)
  const [busy, setBusy] = useState(false)
  const file = useRef(null)
  const openNew = () => setEdit({ id: null, text: JSON.stringify(TEMPLATE[ent] || (list.data?.items?.[0] ? Object.fromEntries(Object.keys(list.data.items[0]).map((k) => [k, ''])) : { id: '' }), null, 2) })
  const save = async () => {
    let body; try { body = JSON.parse(edit.text) } catch { return toast('That is not valid JSON', 'error') }
    setBusy(true)
    try { edit.id ? await api.dataUpdate(ent, edit.id, body) : await api.dataCreate(ent, body); toast('Saved to the database', 'ok'); setEdit(null); list.reload() }
    catch (e) { toast(`${e.message}${e.detail?.errors ? ': ' + e.detail.errors.slice(0, 3).join('; ') : ''}`, 'error') } finally { setBusy(false) }
  }
  const remove = async () => { setBusy(true); try { await api.dataDelete(ent, del); toast('Deleted', 'ok'); setDel(null); list.reload() } catch (e) { toast(`${e.message}${e.detail?.errors ? ': ' + e.detail.errors.slice(0, 2).join('; ') : ''}`, 'error'); setDel(null) } finally { setBusy(false) } }
  const exp = async () => { try { download('dataset.json', JSON.stringify(await api.dataExport(), null, 2)); toast('Dataset exported', 'ok') } catch (e) { toast(e.message, 'error') } }
  const imp = async (e) => {
    const f = e.target.files?.[0]; if (!f) return; e.target.value = ''
    if (!/\.json$/i.test(f.name) || f.size > 5_000_000) return toast('Choose a .json file under 5 MB', 'error')
    try { const r = await api.dataImport(JSON.parse(await f.text())); toast(`Loaded. ${r.next}`, 'ok'); list.reload() } catch (x) { toast(`${x.message}${x.detail?.errors ? ': ' + x.detail.errors.slice(0, 2).join('; ') : ''}`, 'error') }
  }
  return (
    <>
      <PageHeader title="Data" subtitle="Rooms, faculty, groups, courses and sessions. Every change is checked and saved to the database."
        actions={<><input ref={file} type="file" accept=".json" className="sr-only" onChange={imp} aria-label="Import dataset file" /><Btn onClick={() => file.current.click()}><Upload className="h-4 w-4" />Import</Btn><Btn onClick={exp}><Download className="h-4 w-4" />Export</Btn><Btn variant="primary" onClick={openNew}><Plus className="h-4 w-4" />Add</Btn></>} />
      <div className="mb-4"><Tabs value={ent} onChange={setEnt} tabs={Object.keys(ENT).map((k) => ({ id: k, label: k[0].toUpperCase() + k.slice(1) }))} /></div>
      <Async state={list} rows={2} emptyIf={(d) => !d.items.length} empty={<Empty title="Nothing here" />}>{(d) => (
        <Card className="!p-3"><p className="mb-2 px-2 text-xs text-muted">{d.items.length} record(s){d.modified_since_import ? ' · changed since the original import' : ''}</p>
          <Table head={[...ENT[ent], '']}>{d.items.map((r) => (
            <tr key={r.id}>{ENT[ent].map((k) => <td key={k} className="td">{String(r[k] ?? '')}</td>)}
              <td className="td"><div className="flex gap-1.5"><button className="btn !min-h-0 !p-2" aria-label={`Edit ${r.id}`} onClick={() => setEdit({ id: r.id, text: JSON.stringify(r, null, 2) })}><Pencil className="h-4 w-4" /></button>
                <button className="btn !min-h-0 !p-2" aria-label={`Delete ${r.id}`} onClick={() => setDel(r.id)}><Trash2 className="h-4 w-4" /></button></div></td></tr>))}</Table></Card>)}</Async>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? `Edit ${edit.id}` : `Add to ${ent}`} footer={<><Btn onClick={() => setEdit(null)}>Cancel</Btn><Btn variant="primary" loading={busy} onClick={save}>Save</Btn></>}>
        <label htmlFor="rec" className="label">Record (JSON)</label><textarea id="rec" rows={14} className="field font-mono text-xs" value={edit?.text || ''} onChange={(e) => setEdit({ ...edit, text: e.target.value })} />
        <p className="mt-2 text-xs text-muted">Saved only if the whole dataset still passes its integrity checks.</p></Modal>
      <Modal open={!!del} onClose={() => setDel(null)} title={`Delete ${del}?`} footer={<><Btn onClick={() => setDel(null)}>Cancel</Btn><Btn variant="peach" loading={busy} onClick={remove}>Delete</Btn></>}><p>This is refused if anything still uses it.</p></Modal>
    </>
  )
}
