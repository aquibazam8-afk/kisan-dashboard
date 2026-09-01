import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import StaffDashboard from './StaffDashboard.jsx'

// No router dependency for just two static views — /staff picks the
// extension-staff dashboard, everything else stays the farmer app.
const isStaffRoute = window.location.pathname.startsWith('/staff')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isStaffRoute ? <StaffDashboard /> : <App />}
  </StrictMode>,
)
