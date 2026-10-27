import { Routes, Route } from "react-router-dom";
import { ChatView } from "@/components/chat/ChatView";
import { TaskListView } from "@/components/tasks/TaskListView";
import { TaskDetailView } from "@/components/tasks/TaskDetailView";
import { ProjectList } from "@/components/projects/ProjectList";
import { ApprovalList } from "@/components/approvals/ApprovalList";
import { ActivityView } from "@/components/activity/ActivityView";
import { SettingsView } from "@/components/settings/SettingsView";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<ChatView />} />
      <Route path="/tasks" element={<TaskListView />} />
      <Route path="/tasks/:id" element={<TaskDetailView />} />
      <Route path="/projects" element={<ProjectList />} />
      <Route path="/approvals" element={<ApprovalList />} />
      <Route path="/activity" element={<ActivityView />} />
      <Route path="/settings" element={<SettingsView />} />
    </Routes>
  );
}
