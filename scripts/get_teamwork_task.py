"""Minimal script to fetch any Teamwork task and save JSON response to temp file."""
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.connectors.teamwork_client import TeamworkClient

def main():
    client = TeamworkClient()
    
    # Get tasks from the last 30 days to find a task ID
    since = datetime.now(timezone.utc) - timedelta(days=30)
    tasks = client.get_tasks_updated_since(since, include_completed=False)
    
    if not tasks:
        print("No tasks found")
        return
    
    # Get task ID from the first task in the list
    task_id = str(tasks[2].get('id'))
    include_resources = "projects,tasklists,teams,companies,users,tags"
    print(f"Fetching single task with ID: {task_id}")
    print(f"Using endpoint: /projects/api/v3/tasks/{task_id}.json?include={include_resources}")
    print()
    
    # Now fetch the single task using get_task_by_id endpoint with included resources
    task = client.get_task_by_id(task_id, include=include_resources)
    
    if not task:
        print(f"Failed to fetch task {task_id}")
        return
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(task, f, indent=2)
        temp_path = f.name
    
    print(f"Task JSON written to: {temp_path}")
    print()
    print("Task Details:")
    print(f"  ID: {task.get('task', {}).get('id', 'N/A')}")
    print(f"  Name: {task.get('task', {}).get('name', 'N/A')}")
    
    # Show included resources summary
    included = task.get('included', {})
    print()
    print("Included Resources:")
    print(f"  Projects: {len(included.get('projects', {}))}")
    print(f"  Tasklists: {len(included.get('tasklists', {}))}")
    print(f"  Users: {len(included.get('users', {}))}")
    print(f"  Companies: {len(included.get('companies', {}))}")
    print(f"  Teams: {len(included.get('teams', {}))}")
    print(f"  Tags: {len(included.get('tags', {}))}")
    
    # Show project and tasklist names if available
    task_data = task.get('task', {})
    if task_data.get('tasklist'):
        tasklist_id = str(task_data['tasklist'].get('id', ''))
        if tasklist_id and tasklist_id in included.get('tasklists', {}):
            tasklist = included['tasklists'][tasklist_id]
            print()
            print(f"Tasklist: {tasklist.get('name', 'N/A')}")
            if tasklist.get('project'):
                project_id = str(tasklist['project'].get('id', ''))
                if project_id and project_id in included.get('projects', {}):
                    project = included['projects'][project_id]
                    print(f"Project: {project.get('name', 'N/A')} (ID: {project_id})")

if __name__ == "__main__":
    main()

