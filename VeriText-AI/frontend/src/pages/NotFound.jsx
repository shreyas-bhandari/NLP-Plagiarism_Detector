import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { EmptyState } from '../components/Primitives'

export default function NotFound() {
  return (
    <div className="card mx-auto mt-8 max-w-lg">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="That route does not exist in VeriText AI. The dashboard, a new analysis or your history are all one click away."
        action={
          <div className="flex gap-2">
            <Link to="/dashboard" className="btn btn-primary btn-md">
              Dashboard
            </Link>
            <Link to="/analysis/new" className="btn btn-ghost btn-md">
              New analysis
            </Link>
          </div>
        }
      />
    </div>
  )
}
