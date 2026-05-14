import { Link } from 'react-router-dom'
import { ShieldOff } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function UnauthorisedPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-muted">
      <div className="text-center space-y-6 max-w-sm px-6">
        <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto">
          <ShieldOff size={28} className="text-red-500" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-text">Access denied</h1>
          <p className="text-text-muted text-sm">
            You don't have permission to view this page.
          </p>
        </div>
        <div className="flex gap-3 justify-center">
          <Button variant="outline" asChild>
            <Link to="/dashboard">Go to dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
