export default function StatCard({ number, label, note }) {
  return (
    <div className="bg-slate/40 border border-border rounded-card p-4">
      <div className="text-2xl font-bold text-primary-dark">{number}</div>
      <div className="text-sm font-medium text-body mt-0.5">{label}</div>
      {note && <div className="text-[10px] text-muted mt-1">{note}</div>}
    </div>
  )
}
