import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { DndContext, PointerSensor, useDroppable, useSensor, useSensors } from "@dnd-kit/core";
import { useDraggable } from "@dnd-kit/core";
import {
  AlertCircle,
  BarChart3,
  Bot,
  Check,
  CircleDot,
  ClipboardList,
  Clock,
  Columns3,
  GitPullRequest,
  Lock,
  MessageSquare,
  Plus,
  RefreshCw,
  Save,
  UserPlus,
  Users,
} from "lucide-react";
import { api, setCurrentUserId } from "./api";
import "./styles.css";

const columns = [
  ["backlog", "Backlog"],
  ["selected", "Selected"],
  ["in_progress", "In Progress"],
  ["blocked", "Blocked"],
  ["done", "Done"],
];

const priorities = ["low", "medium", "high", "urgent"];

function App() {
  const [users, setUsers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [project, setProject] = useState(null);
  const [sprints, setSprints] = useState([]);
  const [activeSprint, setActiveSprint] = useState(null);
  const [board, setBoard] = useState(null);
  const [summary, setSummary] = useState(null);
  const [velocity, setVelocity] = useState([]);
  const [stories, setStories] = useState([]);
  const [selectedStory, setSelectedStory] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [currentUser, setCurrentUser] = useState("user-001");
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const memberMap = useMemo(() => Object.fromEntries(users.map((user) => [user.id, user])), [users]);

  async function loadInitial() {
    setError("");
    const [userList, projectList] = await Promise.all([api.users(), api.projects()]);
    setUsers(userList);
    setProjects(projectList);
    const nextProjectId = selectedProjectId || projectList[0]?.id || "";
    setSelectedProjectId(nextProjectId);
  }

  async function loadProject(projectId = selectedProjectId) {
    if (!projectId) return;
    setError("");
    const [projectData, sprintData, summaryData, velocityData, storyData] = await Promise.all([
      api.project(projectId),
      api.sprints(projectId),
      api.summary(projectId),
      api.velocity(projectId),
      api.stories(projectId),
    ]);
    const active = sprintData.find((sprint) => sprint.status === "active") || sprintData[0];
    setProject(projectData);
    setSprints(sprintData);
    setActiveSprint(active || null);
    setSummary(summaryData);
    setVelocity(velocityData.sprints || []);
    setStories(storyData);
    if (active) {
      const boardData = await api.board(active.id);
      setBoard(boardData);
      try {
        setReport(await api.getReport(active.id));
      } catch {
        setReport(null);
      }
    } else {
      setBoard(null);
      setReport(null);
    }
  }

  useEffect(() => {
    loadInitial().catch((err) => setError(err.message));
  }, [currentUser]);

  useEffect(() => {
    if (selectedProjectId) {
      loadProject(selectedProjectId).catch((err) => setError(err.message));
    }
  }, [selectedProjectId]);

  async function refresh() {
    setBusy(true);
    try {
      await loadInitial();
      await loadProject();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function changeUser(userId) {
    setCurrentUser(userId);
    setCurrentUserId(userId);
    setProject(null);
    setBoard(null);
  }

  async function moveStory(storyId, status) {
    try {
      const payload = { status };
      if (activeSprint) {
        payload.sprint_id = status === "backlog" ? null : activeSprint.id;
      }
      await api.updateStory(storyId, payload);
      await loadProject();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDragEnd(event) {
    const storyId = event.active?.id;
    const status = event.over?.id;
    if (!storyId || !status || !columns.some(([key]) => key === status)) return;
    await moveStory(storyId, status);
  }

  async function openStory(storyId) {
    try {
      setSelectedStory(await api.story(storyId));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Columns3 size={22} /></div>
          <div>
            <h1>Engineering Workflow Manager</h1>
            <p>Project planning, sprint execution, and reporting.</p>
          </div>
        </div>

        <label className="field">
          <span>Current user</span>
          <select value={currentUser} onChange={(event) => changeUser(event.target.value)}>
            {users.map((user) => (
              <option key={user.id} value={user.id}>{user.name}</option>
            ))}
          </select>
        </label>

        <section className="panel">
          <PanelTitle icon={<ClipboardList size={16} />} title="Projects" />
          <div className="project-list">
            {projects.map((item) => (
              <button
                key={item.id}
                className={item.id === selectedProjectId ? "project-button active" : "project-button"}
                onClick={() => setSelectedProjectId(item.id)}
              >
                <strong>{item.name}</strong>
                <span>{item.members.length} members</span>
              </button>
            ))}
          </div>
          <ProjectForm users={users} onCreate={async (payload) => {
            const created = await api.createProject(payload);
            await loadInitial();
            setSelectedProjectId(created.id);
          }} />
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Active Workspace</p>
            <h2>{project?.name || "No project selected"}</h2>
            <p>{project?.description || "Create or select a project to begin."}</p>
          </div>
          <button className="icon-button" onClick={refresh} disabled={busy} title="Refresh">
            <RefreshCw size={18} />
          </button>
        </header>

        {error && (
          <div className="error-banner">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button onClick={() => setError("")}>Dismiss</button>
          </div>
        )}

        {project && (
          <>
            <Dashboard
              project={project}
              summary={summary}
              activeSprint={activeSprint}
              velocity={velocity}
              sprints={sprints}
              onSprintChange={async (id) => {
                const sprint = sprints.find((item) => item.id === id);
                setActiveSprint(sprint);
                setBoard(await api.board(id));
                try {
                  setReport(await api.getReport(id));
                } catch {
                  setReport(null);
                }
              }}
              onCreateSprint={async (payload) => {
                await api.createSprint(project.id, payload);
                await loadProject();
              }}
              onCloseSprint={async (notes) => {
                if (!activeSprint) return;
                await api.closeSprint(activeSprint.id, { notes });
                await loadProject();
              }}
              onAddMember={async (payload) => {
                await api.addTeamMember(project.id, payload);
                await loadProject();
              }}
              users={users}
            />

            <section className="main-grid">
              <div className="board-panel">
                <div className="section-heading">
                  <PanelTitle icon={<Columns3 size={18} />} title="Sprint Board" />
                  <StoryForm users={project.members} onCreate={async (payload) => {
                    await api.createStory(project.id, payload);
                    await loadProject();
                  }} />
                </div>
                {activeSprint ? (
                  <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
                    <div className="board">
                      {columns.map(([status, label]) => (
                        <BoardColumn
                          key={status}
                          id={status}
                          label={label}
                          stories={board?.columns?.[status] || []}
                          memberMap={memberMap}
                          onStatus={moveStory}
                          onOpen={openStory}
                        />
                      ))}
                    </div>
                  </DndContext>
                ) : (
                  <EmptyState title="No sprint yet" body="Create a sprint to start planning the board." />
                )}
              </div>

              <StoryDrawer
                story={selectedStory}
                stories={stories}
                users={project.members}
                memberMap={memberMap}
                onClose={() => setSelectedStory(null)}
                onRefresh={async () => {
                  if (selectedStory) await openStory(selectedStory.id);
                  await loadProject();
                }}
              />
            </section>

            <ReportPanel
              sprint={activeSprint}
              report={report}
              onDraft={async (additional_context) => {
                if (!activeSprint) return;
                const drafted = await api.draftReport(activeSprint.id, { additional_context });
                setReport(drafted);
              }}
              onSave={async (final_content) => {
                if (!activeSprint) return;
                const saved = await api.saveReport(activeSprint.id, { final_content });
                setReport(saved);
              }}
            />
          </>
        )}
      </section>
    </main>
  );
}

function PanelTitle({ icon, title }) {
  return (
    <div className="panel-title">
      {icon}
      <span>{title}</span>
    </div>
  );
}

function Dashboard({ project, summary, activeSprint, velocity, sprints, onSprintChange, onCreateSprint, onCloseSprint, users, onAddMember }) {
  const counts = summary?.counts || {};
  const [notes, setNotes] = useState("");
  return (
    <section className="dashboard">
      <div className="metric-strip">
        {columns.map(([status, label]) => (
          <div className="metric" key={status}>
            <span>{label}</span>
            <strong>{counts[status] || 0}</strong>
          </div>
        ))}
      </div>
      <div className="dashboard-row">
        <div className="panel">
          <PanelTitle icon={<Clock size={16} />} title="Sprint" />
          <label className="field">
            <span>Selected sprint</span>
            <select value={activeSprint?.id || ""} onChange={(event) => onSprintChange(event.target.value)}>
              {sprints.map((sprint) => (
                <option key={sprint.id} value={sprint.id}>{sprint.name} - {sprint.status}</option>
              ))}
            </select>
          </label>
          <p className="muted">{activeSprint?.goal || "No sprint selected."}</p>
          {activeSprint?.status !== "closed" && activeSprint && (
            <div className="inline-form">
              <input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Closing notes" />
              <button onClick={() => onCloseSprint(notes)}><Lock size={16} /> Close</button>
            </div>
          )}
          <SprintForm onCreate={onCreateSprint} />
        </div>
        <div className="panel">
          <PanelTitle icon={<BarChart3 size={16} />} title="Velocity" />
          <div className="chart">
            {velocity.length === 0 && <p className="muted">Velocity appears after closing a sprint.</p>}
            {velocity.map((item) => (
              <div className="bar-row" key={item.id}>
                <span>{item.name}</span>
                <div><i style={{ width: `${Math.max(8, item.velocity * 14)}px` }} /></div>
                <strong>{item.velocity}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="panel">
          <PanelTitle icon={<Users size={16} />} title="Team" />
          <div className="team-list">
            {project.members.map((member) => <span key={member.id}>{member.name}</span>)}
          </div>
          <AddMemberForm users={users} existing={project.members} onAdd={onAddMember} />
        </div>
      </div>
    </section>
  );
}

function BoardColumn({ id, label, stories, memberMap, onStatus, onOpen }) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <section ref={setNodeRef} className={isOver ? "column over" : "column"}>
      <header>
        <h3>{label}</h3>
        <span>{stories.length}</span>
      </header>
      <div className="cards">
        {stories.map((story) => (
          <StoryCard key={story.id} story={story} member={memberMap[story.assignee_id]} onStatus={onStatus} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}

function StoryCard({ story, member, onStatus, onOpen }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: story.id });
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined;
  return (
    <article ref={setNodeRef} style={style} className="story-card" {...listeners} {...attributes}>
      <button className="story-main" onClick={() => onOpen(story.id)}>
        <span className={`priority ${story.priority}`}>{story.priority}</span>
        <strong>{story.title}</strong>
        <small>{member?.name || "Unassigned"} {story.story_points ? `- ${story.story_points} pts` : ""}</small>
      </button>
      <div className="card-actions">
        {story.blocked_by.length > 0 && <span className="blocked-pill"><GitPullRequest size={13} /> blocked</span>}
        <select value={story.status} onChange={(event) => onStatus(story.id, event.target.value)} onPointerDown={(event) => event.stopPropagation()}>
          {columns.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select>
      </div>
    </article>
  );
}

function StoryDrawer({ story, stories, users, memberMap, onClose, onRefresh }) {
  const [comment, setComment] = useState("");
  const [blockerId, setBlockerId] = useState("");
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setComment("");
    setBlockerId("");
    setSubtaskTitle("");
    setError("");
  }, [story?.id]);

  if (!story) {
    return <aside className="drawer placeholder"><CircleDot size={20} /> Select a story to inspect details.</aside>;
  }
  return (
    <aside className="drawer">
      <button className="drawer-close" onClick={onClose}>Close</button>
      <span className={`priority ${story.priority}`}>{story.priority}</span>
      <h3>{story.title}</h3>
      <p>{story.description || "No description."}</p>
      <dl className="details">
        <div><dt>Status</dt><dd>{story.status}</dd></div>
        <div><dt>Assignee</dt><dd>{memberMap[story.assignee_id]?.name || "Unassigned"}</dd></div>
        <div><dt>Due</dt><dd>{story.due_date || "No date"}</dd></div>
        <div><dt>Points</dt><dd>{story.story_points || "None"}</dd></div>
      </dl>
      {story.acceptance_criteria && <div className="note"><strong>Acceptance criteria</strong><p>{story.acceptance_criteria}</p></div>}
      {error && <p className="form-error">{error}</p>}

      <section className="drawer-section">
        <PanelTitle icon={<GitPullRequest size={16} />} title="Blockers" />
        {story.blocked_by_links.map((link) => (
          <div className="dependency" key={link.id}>
            <span>{stories.find((item) => item.id === link.blocker_story_id)?.title || link.blocker_story_id}</span>
            <small>{link.reason || "No reason given"}</small>
            <button onClick={async () => {
              try {
                await api.removeBlocker(link.blocker_story_id, story.id);
                await onRefresh();
              } catch (err) {
                setError(err.message);
              }
            }}>Remove</button>
          </div>
        ))}
        <div className="inline-form">
          <select value={blockerId} onChange={(event) => setBlockerId(event.target.value)}>
            <option value="">Add blocker</option>
            {stories.filter((item) => item.id !== story.id).map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
          <button onClick={async () => {
            if (!blockerId) return;
            try {
              await api.addBlocker(blockerId, story.id, { reason: "Marked from board detail panel" });
              await onRefresh();
            } catch (err) {
              setError(err.message);
            }
          }}>Add</button>
        </div>
      </section>

      <section className="drawer-section">
        <PanelTitle icon={<Check size={16} />} title="Subtasks" />
        {story.subtasks.map((subtask) => <p className="subtask" key={subtask.id}>{subtask.title} <span>{subtask.status}</span></p>)}
        <div className="inline-form">
          <input value={subtaskTitle} onChange={(event) => setSubtaskTitle(event.target.value)} placeholder="New subtask" />
          <button onClick={async () => {
            if (!subtaskTitle.trim()) return;
            try {
              await api.createSubtask(story.id, { title: subtaskTitle, priority: "medium" });
              await onRefresh();
            } catch (err) {
              setError(err.message);
            }
          }}>Add</button>
        </div>
      </section>

      <section className="drawer-section">
        <PanelTitle icon={<MessageSquare size={16} />} title="Comments" />
        {story.comments.map((item) => (
          <div className="comment" key={item.id}>
            <strong>{memberMap[item.author_id]?.name || item.author_id}</strong>
            <p>{item.text}</p>
          </div>
        ))}
        <div className="comment-box">
          <textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add progress, context, or blocker notes" />
          <button onClick={async () => {
            if (!comment.trim()) return;
            try {
              await api.addComment(story.id, { text: comment });
              await onRefresh();
            } catch (err) {
              setError(err.message);
            }
          }}>Comment</button>
        </div>
      </section>
    </aside>
  );
}

function ReportPanel({ sprint, report, onDraft, onSave }) {
  const [context, setContext] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setContent(report?.final_content || report?.ai_draft || "");
  }, [report?.id, report?.ai_draft, report?.final_content]);

  async function draft() {
    setBusy(true);
    setError("");
    try {
      await onDraft(context);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      await onSave(content);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="report-panel">
      <div className="section-heading">
        <PanelTitle icon={<Bot size={18} />} title="Sprint Report" />
        <span className={sprint?.status === "closed" ? "status-chip closed" : "status-chip"}>{sprint?.status || "none"}</span>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="report-grid">
        <div className="panel">
          <label className="field">
            <span>Additional context</span>
            <textarea value={context} onChange={(event) => setContext(event.target.value)} placeholder="Team interruptions, stakeholder notes, risks, or lessons learned" />
          </label>
          <button disabled={!sprint || sprint.status !== "closed" || busy} onClick={draft}><Bot size={16} /> Generate AI Draft</button>
          <p className="muted">Reports require a closed sprint and an OpenAI API key configured on the backend.</p>
        </div>
        <div className="panel report-editor">
          <textarea value={content} onChange={(event) => setContent(event.target.value)} placeholder="Generate a draft, then edit and save the final report." />
          <button disabled={!content.trim() || busy} onClick={save}><Save size={16} /> Save Final Report</button>
        </div>
      </div>
    </section>
  );
}

function ProjectForm({ users, onCreate }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [members, setMembers] = useState([]);
  if (!open) return <button className="wide-button" onClick={() => setOpen(true)}><Plus size={16} /> New Project</button>;
  return (
    <form className="stack-form" onSubmit={async (event) => {
      event.preventDefault();
      await onCreate({ name, description, team_member_ids: members });
      setOpen(false);
      setName("");
      setDescription("");
      setMembers([]);
    }}>
      <input required value={name} onChange={(event) => setName(event.target.value)} placeholder="Project name" />
      <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Description" />
      <select multiple value={members} onChange={(event) => setMembers(Array.from(event.target.selectedOptions).map((option) => option.value))}>
        {users.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
      </select>
      <button>Create</button>
    </form>
  );
}

function StoryForm({ users, onCreate }) {
  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState({ title: "", description: "", acceptance_criteria: "", priority: "medium", story_points: "", assignee_id: "" });
  if (!open) return <button onClick={() => setOpen(true)}><Plus size={16} /> Story</button>;
  return (
    <form className="story-form" onSubmit={async (event) => {
      event.preventDefault();
      await onCreate({ ...payload, story_points: payload.story_points ? Number(payload.story_points) : null, assignee_id: payload.assignee_id || null });
      setOpen(false);
      setPayload({ title: "", description: "", acceptance_criteria: "", priority: "medium", story_points: "", assignee_id: "" });
    }}>
      <input required value={payload.title} onChange={(event) => setPayload({ ...payload, title: event.target.value })} placeholder="Story title" />
      <input value={payload.description} onChange={(event) => setPayload({ ...payload, description: event.target.value })} placeholder="Description" />
      <select value={payload.priority} onChange={(event) => setPayload({ ...payload, priority: event.target.value })}>
        {priorities.map((priority) => <option key={priority}>{priority}</option>)}
      </select>
      <input type="number" min="1" value={payload.story_points} onChange={(event) => setPayload({ ...payload, story_points: event.target.value })} placeholder="Points" />
      <select value={payload.assignee_id} onChange={(event) => setPayload({ ...payload, assignee_id: event.target.value })}>
        <option value="">Unassigned</option>
        {users.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
      </select>
      <button>Create</button>
    </form>
  );
}

function SprintForm({ onCreate }) {
  const [open, setOpen] = useState(false);
  const [payload, setPayload] = useState({ name: "", goal: "" });
  if (!open) return <button className="secondary-button" onClick={() => setOpen(true)}><Plus size={16} /> New Sprint</button>;
  return (
    <form className="inline-form" onSubmit={async (event) => {
      event.preventDefault();
      await onCreate({ ...payload, status: "active" });
      setOpen(false);
      setPayload({ name: "", goal: "" });
    }}>
      <input value={payload.name} onChange={(event) => setPayload({ ...payload, name: event.target.value })} placeholder="Sprint name" />
      <input value={payload.goal} onChange={(event) => setPayload({ ...payload, goal: event.target.value })} placeholder="Goal" />
      <button>Create</button>
    </form>
  );
}

function AddMemberForm({ users, existing, onAdd }) {
  const [userId, setUserId] = useState("");
  const existingIds = new Set(existing.map((user) => user.id));
  const candidates = users.filter((user) => !existingIds.has(user.id));
  if (candidates.length === 0) return null;
  return (
    <div className="inline-form">
      <select value={userId} onChange={(event) => setUserId(event.target.value)}>
        <option value="">Add member</option>
        {candidates.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
      </select>
      <button onClick={() => userId && onAdd({ user_id: userId, role: "member" })}><UserPlus size={15} /></button>
    </div>
  );
}

function EmptyState({ title, body }) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
