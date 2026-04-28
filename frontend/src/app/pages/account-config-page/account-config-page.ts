import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgClass, NgFor, NgIf } from '@angular/common';
import { TaskService } from '../../task.service';
import { ProjectDto, ContributorDto, GitHubInvitationDto } from '../../task.models';

interface ProjectManageVm {
  project: ProjectDto;
  expanded: boolean;
  newEmail: string;
  contributors: ContributorDto[];
  contributorsLoaded: boolean;
  msg: string;
  msgError: boolean;
}

@Component({
  selector: 'app-account-config-page',
  standalone: true,
  imports: [FormsModule, NgIf, NgFor, NgClass],
  templateUrl: './account-config-page.html',
  styleUrl: './account-config-page.css'
})
export class AccountConfigPageComponent implements OnInit {
  fullName = '';
  email = '';
  githubLogin = '';
  password = '';
  language: 'es' | 'en' | 'pt' = 'es';
  theme: 'light' | 'dark' | 'system' = 'light';
  message = '';
  error = false;
  profileLoading = false;

  currentUserId: string | null = null;
  ownedProjects: ProjectManageVm[] = [];
  projectsLoading = false;
  projectsError = '';

  invitations: GitHubInvitationDto[] = [];
  invitationsLoading = false;
  invitationsError = '';
  invitationMsg = '';

  constructor(
    private readonly taskService: TaskService,
    private readonly cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.currentUserId = this.taskService.getCurrentUserIdFromToken();
    this.loadProfile();
    this.loadOwnedProjects();
    this.loadInvitations();
  }

  private loadProfile(): void {
    if (!this.taskService.getAccessToken()) return;
    this.profileLoading = true;
    this.taskService.getCurrentUser().subscribe({
      next: (user) => {
        this.fullName = user.full_name || '';
        this.email = user.email || '';
        this.githubLogin = user.github_login || '';
        this.profileLoading = false;
        this.cdr.detectChanges();
      },
      error: () => { this.profileLoading = false; this.cdr.detectChanges(); }
    });
  }

  private loadInvitations(): void {
    if (!this.taskService.getAccessToken()) return;
    this.invitationsLoading = true;
    this.taskService.getGitHubInvitations().subscribe({
      next: (res) => {
        this.invitations = res.invitations || [];
        this.invitationsLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.invitationsLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  acceptInvitation(inv: GitHubInvitationDto): void {
    this.taskService.acceptGitHubInvitation(inv.id).subscribe({
      next: () => {
        this.invitations = this.invitations.filter(i => i.id !== inv.id);
        this.invitationMsg = `Invitación a "${inv.repo}" aceptada.`;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.invitationMsg = err?.error?.error || 'No se pudo aceptar la invitación.';
        this.cdr.detectChanges();
      }
    });
  }

  declineInvitation(inv: GitHubInvitationDto): void {
    this.taskService.declineGitHubInvitation(inv.id).subscribe({
      next: () => {
        this.invitations = this.invitations.filter(i => i.id !== inv.id);
        this.invitationMsg = `Invitación a "${inv.repo}" rechazada.`;
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.invitationMsg = err?.error?.error || 'No se pudo rechazar la invitación.';
        this.cdr.detectChanges();
      }
    });
  }

  save() {
    if (this.fullName.trim().length < 2) {
      this.error = true;
      this.message = 'El nombre debe tener al menos 2 caracteres.';
      return;
    }
    this.error = false;
    this.message = `Configuración guardada para ${this.fullName}.`;
    this.password = '';
  }

  private loadOwnedProjects(): void {
    if (!this.taskService.getAccessToken()) return;
    this.projectsLoading = true;
    this.projectsError = '';
    this.taskService.getAccessibleProjects().subscribe({
      next: (res) => {
        this.projectsLoading = false;
        const owned = (res.projects || []).filter(p => p.author_id === this.currentUserId);
        this.ownedProjects = owned.map(p => ({
          project: p,
          expanded: false,
          newEmail: '',
          contributors: this._buildContributorList(p),
          contributorsLoaded: false,
          msg: '',
          msgError: false,
        }));
        this.cdr.detectChanges();
      },
      error: () => {
        this.projectsLoading = false;
        this.projectsError = 'No se pudieron cargar los proyectos.';
        this.cdr.detectChanges();
      }
    });
  }

  private _buildContributorList(p: ProjectDto): ContributorDto[] {
    return (p.contributor_ids || []).map(id => ({ id, email: '…', full_name: '' }));
  }

  toggleProject(vm: ProjectManageVm): void {
    vm.expanded = !vm.expanded;
    this.cdr.detectChanges();
  }

  addContributor(vm: ProjectManageVm): void {
    const email = vm.newEmail.trim();
    if (!email) return;
    vm.msg = '';
    vm.msgError = false;
    this.taskService.addContributor(vm.project.id, email).subscribe({
      next: (res) => {
        vm.contributors = [...vm.contributors, res.contributor];
        vm.newEmail = '';
        vm.msg = res.contributor.email + ' añadido como colaborador.'
          + ((res as any).github_warning ? ` (Aviso GitHub: ${(res as any).github_warning})` : '');
        vm.msgError = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        vm.msg = err?.error?.message || err?.error?.error || 'No se pudo añadir el colaborador.';
        vm.msgError = true;
        this.cdr.detectChanges();
      }
    });
  }

  removeContributor(vm: ProjectManageVm, contributor: ContributorDto): void {
    this.taskService.removeContributor(vm.project.id, contributor.id).subscribe({
      next: () => {
        vm.contributors = vm.contributors.filter(c => c.id !== contributor.id);
        vm.msg = `${contributor.email} eliminado.`;
        vm.msgError = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        vm.msg = err?.error?.message || err?.error?.error || 'No se pudo eliminar el colaborador.';
        vm.msgError = true;
        this.cdr.detectChanges();
      }
    });
  }

  deleteProject(vm: ProjectManageVm): void {
    if (!confirm(`¿Seguro que quieres eliminar el proyecto "${vm.project.name}"? Esta acción no se puede deshacer.`)) return;
    this.taskService.deleteProject(vm.project.id).subscribe({
      next: () => {
        this.ownedProjects = this.ownedProjects.filter(v => v.project.id !== vm.project.id);
        this.cdr.detectChanges();
      },
      error: (err) => {
        vm.msg = err?.error?.message || err?.error?.error || 'No se pudo eliminar el proyecto.';
        vm.msgError = true;
        vm.expanded = true;
        this.cdr.detectChanges();
      }
    });
  }
}
