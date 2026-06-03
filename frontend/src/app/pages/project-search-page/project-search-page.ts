import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AsyncPipe, NgFor, NgIf } from '@angular/common';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { TaskService } from '../../task.service';
import { AuthService } from '../../auth.service';
import { PublicProjectDto, ProjectDto } from '../../task.models';

type Tab = 'public' | 'private';

@Component({
  selector: 'app-project-search-page',
  standalone: true,
  imports: [FormsModule, NgFor, NgIf, AsyncPipe],
  templateUrl: './project-search-page.html',
  styleUrl: './project-search-page.css'
})
export class ProjectSearchPageComponent implements OnInit {
  // Auth
  get isLoggedIn$() { return this.auth.isLoggedIn$; }
  private isLoggedIn = false;

  // Tab
  activeTab: Tab = 'public';

  // Public tab
  publicProjects: PublicProjectDto[] = [];
  publicLoading = false;
  publicError = '';
  publicQuery = '';
  selectedPublic: PublicProjectDto | null = null;
  followingInProgress: Set<string> = new Set();
  private publicSearch$ = new Subject<string>();

  // Private tab (own + contributed — requires auth)
  privateProjects: ProjectDto[] = [];
  privateLoading = false;
  privateError = '';
  privateQuery = '';
  selectedPrivate: ProjectDto | null = null;
  private currentUserId = '';

  constructor(
    private readonly taskService: TaskService,
    private readonly auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.auth.isLoggedIn$.subscribe(logged => {
      this.isLoggedIn = logged;
      if (logged) {
        this.currentUserId = this.taskService.getCurrentUserIdFromToken() || '';
      }
    });

    // Debounced public search
    this.publicSearch$.pipe(debounceTime(350), distinctUntilChanged()).subscribe(q => {
      this._fetchPublic(q);
    });

    this._fetchPublic('');
  }

  // ── Public tab ─────────────────────────────────────────────────────────────

  onPublicQueryChange(): void {
    this.publicSearch$.next(this.publicQuery);
  }

  private _fetchPublic(q: string): void {
    this.publicLoading = true;
    this.publicError = '';
    this.taskService.searchPublicProjects(q, 1, 60).subscribe({
      next: res => {
        this.publicProjects = res.projects;
        if (this.selectedPublic) {
          this.selectedPublic = this.publicProjects.find(p => p.id === this.selectedPublic!.id) ?? this.publicProjects[0] ?? null;
        } else {
          this.selectedPublic = this.publicProjects[0] ?? null;
        }
        this.publicLoading = false;
      },
      error: () => {
        this.publicError = 'No se pudieron cargar los proyectos públicos.';
        this.publicLoading = false;
      }
    });
  }

  selectPublic(p: PublicProjectDto): void {
    this.selectedPublic = p;
  }

  toggleFollow(p: PublicProjectDto): void {
    if (!this.isLoggedIn || this.followingInProgress.has(p.id)) return;
    this.followingInProgress.add(p.id);
    const action$ = p.is_following
      ? this.taskService.unfollowProject(p.id)
      : this.taskService.followProject(p.id);
    action$.subscribe({
      next: () => {
        p.is_following = !p.is_following;
        if (this.selectedPublic?.id === p.id) {
          this.selectedPublic = { ...p };
        }
        this.followingInProgress.delete(p.id);
      },
      error: () => this.followingInProgress.delete(p.id)
    });
  }

  progressAll(p: PublicProjectDto): number {
    if (!p.total_nodes) return 0;
    return Math.round((p.validated_nodes / p.total_nodes) * 100);
  }

  progressLeaves(p: PublicProjectDto): number {
    if (!p.total_leaves) return 0;
    return Math.round((p.validated_leaves / p.total_leaves) * 100);
  }

  // ── Private tab ────────────────────────────────────────────────────────────

  switchTab(tab: Tab): void {
    this.activeTab = tab;
    if (tab === 'private' && this.isLoggedIn && this.privateProjects.length === 0 && !this.privateLoading) {
      this._fetchPrivate();
    }
  }

  private _fetchPrivate(): void {
    this.privateLoading = true;
    this.privateError = '';
    this.taskService.getAccessibleProjects().subscribe({
      next: res => {
        // Only own + contributed private projects (exclude followed public ones)
        this.privateProjects = res.projects.filter(
          p => p.visibility === 'private' &&
               (p.author_id === this.currentUserId || (p.contributor_ids ?? []).includes(this.currentUserId))
        );
        this.selectedPrivate = this.privateProjects[0] ?? null;
        this.privateLoading = false;
      },
      error: () => {
        this.privateError = 'No se pudieron cargar los proyectos privados.';
        this.privateLoading = false;
      }
    });
  }

  get filteredPrivate(): ProjectDto[] {
    const q = this.privateQuery.trim().toLowerCase();
    return q
      ? this.privateProjects.filter(p => p.name.toLowerCase().includes(q))
      : this.privateProjects;
  }

  selectPrivate(p: ProjectDto): void {
    this.selectedPrivate = p;
  }

  isOwner(p: ProjectDto): boolean {
    return p.author_id === this.currentUserId;
  }
}

