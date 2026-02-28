import { useState, useEffect } from 'react'
import GroupAddIcon from '@mui/icons-material/GroupAdd'
import PersonAddIcon from '@mui/icons-material/PersonAdd'
import CloseIcon from '@mui/icons-material/Close'
import { apiGet, apiPost, apiPut } from '../utils/api'
import './AdminPanel.css'

function AdminPanel({ user }) {
  const [teams, setTeams] = useState([])
  const [users, setUsers] = useState([])
  const [showCreateTeam, setShowCreateTeam] = useState(false)
  const [showAddMember, setShowAddMember] = useState(false)
  const [selectedTeam, setSelectedTeam] = useState(null)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const [teamForm, setTeamForm] = useState({
    team_name: '',
    description: ''
  })

  const [memberForm, setMemberForm] = useState({
    user_id: '',
    role: 'employee'
  })

  useEffect(() => {
    loadTeams()
    loadUsers()
  }, [])

  const loadTeams = async () => {
    try {
      const response = await apiGet('/api/teams')
      const data = await response.json()
      setTeams(data)
    } catch (err) {
      console.error('Failed to load teams:', err)
    }
  }

  const loadUsers = async () => {
    try {
      const response = await apiGet('/api/users')
      if (response.ok) {
        const data = await response.json()
        setUsers(data)
      }
    } catch (err) {
      console.error('Failed to load users:', err)
    }
  }

  const handleCreateTeam = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const response = await apiPost('/api/teams', teamForm)

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to create team')
      }

      setSuccess('Team created successfully!')
      setTeamForm({ team_name: '', description: '' })
      setShowCreateTeam(false)
      loadTeams()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleAddMember = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const response = await apiPut(
        `/api/teams/${selectedTeam.team_id}/assign`,
        memberForm
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to add member')
      }

      setSuccess('Member added successfully!')
      setMemberForm({ user_id: '', role: 'employee' })
      setShowAddMember(false)
      setSelectedTeam(null)
      loadTeams()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const openAddMemberModal = (team) => {
    setSelectedTeam(team)
    setShowAddMember(true)
    setError('')
  }

  // Filter users who are not in the selected team
  const availableUsers = selectedTeam
    ? users.filter(u => u.team_id !== selectedTeam.team_id)
    : []

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <h2>Team Management</h2>
        <button
          className="btn-create-team"
          onClick={() => setShowCreateTeam(true)}
        >
          <GroupAddIcon sx={{ fontSize: '1.1rem' }} />
          Create Team
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          {error}
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          {success}
        </div>
      )}

      <div className="teams-grid">
        {teams.length === 0 ? (
          <div className="empty-state">
            <GroupAddIcon sx={{ fontSize: '4rem', opacity: 0.3 }} />
            <p>No teams yet. Create your first team!</p>
          </div>
        ) : (
          teams.map((team) => (
            <div key={team.team_id} className="team-card">
              <div className="team-card-header">
                <h3>{team.team_name}</h3>
                <span className="member-count">
                  {team.members?.length || 0} members
                </span>
              </div>
              {team.description && (
                <p className="team-description">{team.description}</p>
              )}
              <div className="team-members">
                {team.members && team.members.length > 0 ? (
                  <ul>
                    {team.members.map((member) => (
                      <li key={member.user_id}>
                        <span className="member-name">{member.full_name}</span>
                        <span className={`member-role role-${member.role}`}>
                          {member.role.replace('_', ' ')}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="no-members">No members yet</p>
                )}
              </div>
              <button
                className="btn-add-member"
                onClick={() => openAddMemberModal(team)}
              >
                <PersonAddIcon sx={{ fontSize: '1rem' }} />
                Add Member
              </button>
            </div>
          ))
        )}
      </div>

      {/* Create Team Modal */}
      {showCreateTeam && (
        <div className="modal-overlay" onClick={() => setShowCreateTeam(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Create New Team</h3>
              <button
                className="btn-close"
                onClick={() => setShowCreateTeam(false)}
              >
                <CloseIcon />
              </button>
            </div>
            <form onSubmit={handleCreateTeam}>
              <div className="form-group">
                <label htmlFor="team_name">Team Name *</label>
                <input
                  type="text"
                  id="team_name"
                  value={teamForm.team_name}
                  onChange={(e) =>
                    setTeamForm({ ...teamForm, team_name: e.target.value })
                  }
                  placeholder="e.g., Engineering Team"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="description">Description</label>
                <textarea
                  id="description"
                  value={teamForm.description}
                  onChange={(e) =>
                    setTeamForm({ ...teamForm, description: e.target.value })
                  }
                  placeholder="Brief description of the team..."
                  rows={3}
                />
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setShowCreateTeam(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-submit" disabled={loading}>
                  {loading ? 'Creating...' : 'Create Team'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Member Modal */}
      {showAddMember && selectedTeam && (
        <div className="modal-overlay" onClick={() => setShowAddMember(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Add Member to {selectedTeam.team_name}</h3>
              <button
                className="btn-close"
                onClick={() => setShowAddMember(false)}
              >
                <CloseIcon />
              </button>
            </div>
            <form onSubmit={handleAddMember}>
              <div className="form-group">
                <label htmlFor="user_id">Select User *</label>
                <select
                  id="user_id"
                  value={memberForm.user_id}
                  onChange={(e) =>
                    setMemberForm({ ...memberForm, user_id: e.target.value })
                  }
                  required
                >
                  <option value="">Choose a user...</option>
                  {availableUsers.map((user) => (
                    <option key={user.user_id} value={user.user_id}>
                      {user.full_name} ({user.email})
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="role">Role *</label>
                <select
                  id="role"
                  value={memberForm.role}
                  onChange={(e) =>
                    setMemberForm({ ...memberForm, role: e.target.value })
                  }
                  required
                >
                  <option value="employee">Employee</option>
                  <option value="team_lead">Team Lead</option>
                </select>
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-cancel"
                  onClick={() => setShowAddMember(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-submit" disabled={loading}>
                  {loading ? 'Adding...' : 'Add Member'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default AdminPanel
