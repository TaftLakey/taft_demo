const API_BASE = import.meta.env.VITE_API_BASE || "/api";

let currentUserId = localStorage.getItem("workflow-user-id") || "user-001";

export function setCurrentUserId(userId) {
  currentUserId = userId;
  localStorage.setItem("workflow-user-id", userId);
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": currentUserId,
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(data?.detail || "Request failed");
  }
  return data;
}

export const api = {
  users: () => request("/users"),
  projects: () => request("/projects"),
  createProject: (payload) => request("/projects", { method: "POST", body: JSON.stringify(payload) }),
  project: (id) => request(`/projects/${id}`),
  addTeamMember: (projectId, payload) => request(`/projects/${projectId}/team`, { method: "POST", body: JSON.stringify(payload) }),
  summary: (projectId) => request(`/projects/${projectId}/summary`),
  velocity: (projectId) => request(`/projects/${projectId}/velocity`),
  stories: (projectId) => request(`/projects/${projectId}/stories`),
  createStory: (projectId, payload) => request(`/projects/${projectId}/stories`, { method: "POST", body: JSON.stringify(payload) }),
  story: (id) => request(`/stories/${id}`),
  updateStory: (id, payload) => request(`/stories/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  createSubtask: (id, payload) => request(`/stories/${id}/subtasks`, { method: "POST", body: JSON.stringify(payload) }),
  addComment: (id, payload) => request(`/stories/${id}/comments`, { method: "POST", body: JSON.stringify(payload) }),
  addBlocker: (blockerId, blockedId, payload) =>
    request(`/stories/${blockerId}/blocks/${blockedId}`, { method: "POST", body: JSON.stringify(payload) }),
  removeBlocker: (blockerId, blockedId) => request(`/stories/${blockerId}/blocks/${blockedId}`, { method: "DELETE" }),
  sprints: (projectId) => request(`/projects/${projectId}/sprints`),
  createSprint: (projectId, payload) => request(`/projects/${projectId}/sprints`, { method: "POST", body: JSON.stringify(payload) }),
  updateSprint: (id, payload) => request(`/sprints/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  board: (sprintId) => request(`/sprints/${sprintId}/board`),
  closeSprint: (sprintId, payload) => request(`/sprints/${sprintId}/close`, { method: "POST", body: JSON.stringify(payload) }),
  draftReport: (sprintId, payload) => request(`/sprints/${sprintId}/report/draft`, { method: "POST", body: JSON.stringify(payload) }),
  getReport: (sprintId) => request(`/sprints/${sprintId}/report`),
  saveReport: (sprintId, payload) => request(`/sprints/${sprintId}/report`, { method: "PUT", body: JSON.stringify(payload) }),
};

