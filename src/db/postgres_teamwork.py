"""PostgreSQL operations for Teamwork entities."""
from typing import Dict, Any, List
from psycopg2.extras import Json

from src.logging_conf import logger


class PostgresTeamworkOps:
    """Teamwork entity operations."""
    
    def upsert_tw_company(self, company_data: Dict[str, Any]) -> None:
        """Upsert a Teamwork company."""
        try:
            company_id = int(company_data.get("id"))
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tw_companies (
                        id, name, address_one, address_two, city, state, zip, country_code,
                        phone, fax, email_one, email_two, email_three, website, industry_id,
                        logo_url, can_see_private, is_owner, status, private_notes,
                        private_notes_text, profile_text, created_at, updated_at, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        address_one = EXCLUDED.address_one,
                        address_two = EXCLUDED.address_two,
                        city = EXCLUDED.city,
                        state = EXCLUDED.state,
                        zip = EXCLUDED.zip,
                        country_code = EXCLUDED.country_code,
                        phone = EXCLUDED.phone,
                        fax = EXCLUDED.fax,
                        email_one = EXCLUDED.email_one,
                        email_two = EXCLUDED.email_two,
                        email_three = EXCLUDED.email_three,
                        website = EXCLUDED.website,
                        industry_id = EXCLUDED.industry_id,
                        logo_url = EXCLUDED.logo_url,
                        can_see_private = EXCLUDED.can_see_private,
                        is_owner = EXCLUDED.is_owner,
                        status = EXCLUDED.status,
                        private_notes = EXCLUDED.private_notes,
                        private_notes_text = EXCLUDED.private_notes_text,
                        profile_text = EXCLUDED.profile_text,
                        updated_at = EXCLUDED.updated_at,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    company_id,
                    company_data.get("name"),
                    company_data.get("addressOne"),
                    company_data.get("addressTwo"),
                    company_data.get("city"),
                    company_data.get("state"),
                    company_data.get("zip"),
                    company_data.get("countryCode"),
                    company_data.get("phone"),
                    company_data.get("fax"),
                    company_data.get("emailOne"),
                    company_data.get("emailTwo"),
                    company_data.get("emailThree"),
                    company_data.get("website"),
                    int(company_data["industryId"]) if company_data.get("industryId") else None,
                    company_data.get("logoUrl"),
                    company_data.get("canSeePrivate"),
                    company_data.get("isOwner"),
                    company_data.get("status"),
                    company_data.get("privateNotes"),
                    company_data.get("privateNotesText"),
                    company_data.get("profileText"),
                    self._parse_dt(company_data.get("createdAt")),
                    self._parse_dt(company_data.get("updatedAt")),
                    Json(company_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted company {company_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert company: {e}", exc_info=True)
    
    def upsert_tw_user(self, user_data: Dict[str, Any]) -> None:
        """Upsert a Teamwork user."""
        try:
            user_id = int(user_data.get("id"))
            
            # Extract company ID from nested object
            company_id = None
            if user_data.get("company"):
                if isinstance(user_data["company"], dict):
                    company_id = int(user_data["company"]["id"]) if user_data["company"].get("id") else None
            elif user_data.get("companyId"):
                company_id = int(user_data["companyId"])
            
            # Validate that company exists before setting foreign key
            company_id = self._validate_fk_exists("tw_companies", company_id)
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tw_users (
                        id, first_name, last_name, email, avatar_url, title, company_id,
                        company_role_id, is_admin, is_client_user, is_placeholder_resource,
                        is_service_account, deleted, can_add_projects, can_access_portfolio,
                        can_manage_portfolio, timezone, length_of_day, user_cost, user_rate,
                        last_login, created_at, updated_at, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email,
                        avatar_url = EXCLUDED.avatar_url,
                        title = EXCLUDED.title,
                        company_id = EXCLUDED.company_id,
                        company_role_id = EXCLUDED.company_role_id,
                        is_admin = EXCLUDED.is_admin,
                        is_client_user = EXCLUDED.is_client_user,
                        is_placeholder_resource = EXCLUDED.is_placeholder_resource,
                        is_service_account = EXCLUDED.is_service_account,
                        deleted = EXCLUDED.deleted,
                        can_add_projects = EXCLUDED.can_add_projects,
                        can_access_portfolio = EXCLUDED.can_access_portfolio,
                        can_manage_portfolio = EXCLUDED.can_manage_portfolio,
                        timezone = EXCLUDED.timezone,
                        length_of_day = EXCLUDED.length_of_day,
                        user_cost = EXCLUDED.user_cost,
                        user_rate = EXCLUDED.user_rate,
                        last_login = EXCLUDED.last_login,
                        updated_at = EXCLUDED.updated_at,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    user_id,
                    user_data.get("firstName"),
                    user_data.get("lastName"),
                    user_data.get("email"),
                    user_data.get("avatarUrl"),
                    user_data.get("title"),
                    company_id,
                    int(user_data["companyRoleId"]) if user_data.get("companyRoleId") else None,
                    user_data.get("isAdmin"),
                    user_data.get("isClientUser"),
                    user_data.get("isPlaceholderResource"),
                    user_data.get("isServiceAccount"),
                    user_data.get("deleted", False),
                    user_data.get("canAddProjects"),
                    user_data.get("canAccessPortfolio"),
                    user_data.get("canManagePortfolio"),
                    user_data.get("timezone"),
                    user_data.get("lengthOfDay"),
                    user_data.get("userCost"),
                    user_data.get("userRate"),
                    self._parse_dt(user_data.get("lastLogin")),
                    self._parse_dt(user_data.get("createdAt")),
                    self._parse_dt(user_data.get("updatedAt")),
                    Json(user_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted user {user_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert user: {e}", exc_info=True)
    
    def upsert_tw_team(self, team_data: Dict[str, Any]) -> None:
        """Upsert a Teamwork team."""
        try:
            team_id = int(team_data.get("id"))
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tw_teams (
                        id, name, handle, team_logo, team_logo_color, team_logo_icon,
                        created_at, updated_at, raw_data
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        handle = EXCLUDED.handle,
                        team_logo = EXCLUDED.team_logo,
                        team_logo_color = EXCLUDED.team_logo_color,
                        team_logo_icon = EXCLUDED.team_logo_icon,
                        updated_at = EXCLUDED.updated_at,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    team_id,
                    team_data.get("name"),
                    team_data.get("handle"),
                    team_data.get("teamLogo"),
                    team_data.get("teamLogoColor"),
                    team_data.get("teamLogoIcon"),
                    self._parse_dt(team_data.get("createdAt")),
                    self._parse_dt(team_data.get("updatedAt")),
                    Json(team_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted team {team_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert team: {e}", exc_info=True)
    
    def upsert_tw_tag(self, tag_data: Dict[str, Any]) -> None:
        """Upsert a Teamwork tag."""
        try:
            tag_id = int(tag_data.get("id"))
            
            # Extract project ID from nested object
            project_id = None
            if tag_data.get("project"):
                if isinstance(tag_data["project"], dict):
                    project_id = int(tag_data["project"]["id"]) if tag_data["project"].get("id") else None
            elif tag_data.get("projectId"):
                project_id = int(tag_data["projectId"])
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tw_tags (
                        id, name, color, project_id, count, raw_data
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        color = EXCLUDED.color,
                        project_id = EXCLUDED.project_id,
                        count = EXCLUDED.count,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    tag_id,
                    tag_data.get("name"),
                    tag_data.get("color"),
                    project_id,
                    tag_data.get("count", 0),
                    Json(tag_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted tag {tag_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert tag: {e}", exc_info=True)
    
    def upsert_tw_project(self, project_data: Dict[str, Any]) -> None:
        """Upsert a Teamwork project."""
        try:
            project_id = int(project_data.get("id"))
            
            # Extract related IDs from nested objects
            company_id = self._extract_id(project_data.get("company") or project_data.get("companyId"))
            owner_id = self._extract_id(project_data.get("ownedBy") or project_data.get("ownerId"))
            category_id = self._extract_id(project_data.get("category") or project_data.get("categoryId"))
            completed_by = self._extract_id(project_data.get("completedBy"))
            created_by = self._extract_id(project_data.get("createdBy"))
            updated_by = self._extract_id(project_data.get("updatedBy"))
            
            # Validate foreign keys exist
            company_id = self._validate_fk_exists("tw_companies", company_id)
            owner_id = self._validate_fk_exists("tw_users", owner_id)
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tw_projects (
                        id, name, description, company_id, owner_id, category_id, status, sub_status,
                        start_date, end_date, start_at, end_at, completed_at, completed_by,
                        created_by, updated_by, is_starred, is_billable, is_sample_project,
                        is_onboarding_project, is_project_admin, logo, logo_color, logo_icon,
                        announcement, show_announcement, default_privacy, privacy_enabled,
                        harvest_timers_enabled, notify_everyone, skip_weekends,
                        created_at, updated_at, last_worked_on, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        company_id = EXCLUDED.company_id,
                        owner_id = EXCLUDED.owner_id,
                        category_id = EXCLUDED.category_id,
                        status = EXCLUDED.status,
                        sub_status = EXCLUDED.sub_status,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        start_at = EXCLUDED.start_at,
                        end_at = EXCLUDED.end_at,
                        completed_at = EXCLUDED.completed_at,
                        completed_by = EXCLUDED.completed_by,
                        updated_by = EXCLUDED.updated_by,
                        is_starred = EXCLUDED.is_starred,
                        is_billable = EXCLUDED.is_billable,
                        logo = EXCLUDED.logo,
                        logo_color = EXCLUDED.logo_color,
                        logo_icon = EXCLUDED.logo_icon,
                        announcement = EXCLUDED.announcement,
                        show_announcement = EXCLUDED.show_announcement,
                        default_privacy = EXCLUDED.default_privacy,
                        privacy_enabled = EXCLUDED.privacy_enabled,
                        harvest_timers_enabled = EXCLUDED.harvest_timers_enabled,
                        notify_everyone = EXCLUDED.notify_everyone,
                        skip_weekends = EXCLUDED.skip_weekends,
                        updated_at = EXCLUDED.updated_at,
                        last_worked_on = EXCLUDED.last_worked_on,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    project_id,
                    project_data.get("name"),
                    project_data.get("description"),
                    company_id,
                    owner_id,
                    category_id,
                    project_data.get("status"),
                    project_data.get("subStatus"),
                    self._parse_date(project_data.get("startDate")),
                    self._parse_date(project_data.get("endDate")),
                    self._parse_dt(project_data.get("startAt")),
                    self._parse_dt(project_data.get("endAt")),
                    self._parse_dt(project_data.get("completedAt")),
                    completed_by,
                    created_by,
                    updated_by,
                    project_data.get("isStarred"),
                    project_data.get("isBillable"),
                    project_data.get("isSampleProject"),
                    project_data.get("isOnBoardingProject"),
                    project_data.get("isProjectAdmin"),
                    project_data.get("logo"),
                    project_data.get("logoColor"),
                    project_data.get("logoIcon"),
                    project_data.get("announcement"),
                    project_data.get("showAnnouncement"),
                    project_data.get("defaultPrivacy"),
                    project_data.get("privacyEnabled"),
                    project_data.get("harvestTimersEnabled"),
                    project_data.get("notifyEveryone"),
                    project_data.get("skipWeekends"),
                    self._parse_dt(project_data.get("createdAt")),
                    self._parse_dt(project_data.get("updatedAt")),
                    self._parse_dt(project_data.get("lastWorkedOn")),
                    Json(project_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted project {project_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert project: {e}", exc_info=True)
    
    def upsert_tw_tasklist(self, tasklist_data: Dict[str, Any]) -> None:
        """Upsert a Teamwork tasklist."""
        try:
            tasklist_id = int(tasklist_data.get("id"))
            
            # Extract project ID from nested object
            project_id = self._extract_id(tasklist_data.get("project") or tasklist_data.get("projectId"))
            milestone_id = self._extract_id(tasklist_data.get("milestone") or tasklist_data.get("milestoneId"))
            
            # Validate foreign keys exist
            project_id = self._validate_fk_exists("tw_projects", project_id)
            
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tw_tasklists (
                        id, name, description, project_id, milestone_id, status, display_order,
                        is_private, is_pinned, is_billable, icon, lockdown_id,
                        calculated_start_date, calculated_due_date, created_at, updated_at, raw_data
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        project_id = EXCLUDED.project_id,
                        milestone_id = EXCLUDED.milestone_id,
                        status = EXCLUDED.status,
                        display_order = EXCLUDED.display_order,
                        is_private = EXCLUDED.is_private,
                        is_pinned = EXCLUDED.is_pinned,
                        is_billable = EXCLUDED.is_billable,
                        icon = EXCLUDED.icon,
                        lockdown_id = EXCLUDED.lockdown_id,
                        calculated_start_date = EXCLUDED.calculated_start_date,
                        calculated_due_date = EXCLUDED.calculated_due_date,
                        updated_at = EXCLUDED.updated_at,
                        raw_data = EXCLUDED.raw_data,
                        db_updated_at = NOW()
                """, (
                    tasklist_id,
                    tasklist_data.get("name"),
                    tasklist_data.get("description"),
                    project_id,
                    milestone_id,
                    tasklist_data.get("status"),
                    tasklist_data.get("displayOrder"),
                    tasklist_data.get("isPrivate"),
                    tasklist_data.get("isPinned"),
                    tasklist_data.get("isBillable"),
                    tasklist_data.get("icon"),
                    int(tasklist_data["lockdownId"]) if tasklist_data.get("lockdownId") else None,
                    self._parse_date(tasklist_data.get("calculatedStartDate")),
                    self._parse_date(tasklist_data.get("calculatedDueDate")),
                    self._parse_dt(tasklist_data.get("createdAt")),
                    self._parse_dt(tasklist_data.get("updatedAt")),
                    Json(tasklist_data)
                ))
                self.conn.commit()
                logger.debug(f"Upserted tasklist {tasklist_id}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to upsert tasklist: {e}", exc_info=True)
    
    def link_task_tags(self, task_id: str, tag_ids: List[int]) -> None:
        """Link a task to tags (many-to-many)."""
        try:
            with self.conn.cursor() as cur:
                # Clear existing links
                cur.execute("DELETE FROM task_tags WHERE task_id = %s", (task_id,))
                
                # Insert new links
                for tag_id in tag_ids:
                    cur.execute("""
                        INSERT INTO task_tags (task_id, tag_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (task_id, tag_id))
                
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to link task tags: {e}", exc_info=True)
    
    def link_task_assignees(self, task_id: str, user_ids: List[int]) -> None:
        """Link a task to assignees (many-to-many)."""
        try:
            with self.conn.cursor() as cur:
                # Clear existing links
                cur.execute("DELETE FROM task_assignees WHERE task_id = %s", (task_id,))
                
                # Insert new links
                for user_id in user_ids:
                    cur.execute("""
                        INSERT INTO task_assignees (task_id, user_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (task_id, user_id))
                
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to link task assignees: {e}", exc_info=True)
    
    def link_user_teams(self, user_id: int, team_ids: List[int]) -> None:
        """Link a user to teams (many-to-many)."""
        try:
            with self.conn.cursor() as cur:
                # Clear existing links
                cur.execute("DELETE FROM tw_user_teams WHERE user_id = %s", (user_id,))
                
                # Insert new links
                for team_id in team_ids:
                    cur.execute("""
                        INSERT INTO tw_user_teams (user_id, team_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                    """, (user_id, team_id))
                
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to link user teams: {e}", exc_info=True)

