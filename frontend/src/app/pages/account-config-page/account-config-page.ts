import { ChangeDetectorRef, Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { KeyValuePipe, NgClass, NgFor, NgIf } from '@angular/common';
import { TaskService } from '../../task.service';
import { ProjectDto, ContributorDto, GitHubInvitationDto, AvailableModel, ApiKeyStatus } from '../../task.models';
import { UserPreferencesService, DEFAULT_SYSTEM_PROMPTS, SystemPromptDef } from '../../user-preferences.service';

interface ProjectManageVm {
  project: ProjectDto;
  expanded: boolean;
  newEmail: string;
  contributors: ContributorDto[];
  contributorsLoaded: boolean;
  msg: string;
  msgError: boolean;
}

interface ModelKeyVm {
  model: AvailableModel;
  status: ApiKeyStatus | null;
  keyInput: string;
  saving: boolean;
  saved: boolean;
  error: string;
}

@Component({
  selector: 'app-account-config-page',
  standalone: true,
  imports: [FormsModule, KeyValuePipe, NgIf, NgFor, NgClass],
  templateUrl: './account-config-page.html',
  styleUrl: './account-config-page.css'
})
export class AccountConfigPageComponent implements OnInit, OnDestroy {
  fullName = '';
  email = '';
  githubLogin = '';
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

  // ── IA & Modelos ──────────────────────────────────────────────────────────
  modelVms: ModelKeyVm[] = [];
  modelsLoading = false;
  defaultModelId = '';
  defaultModelSaved = false;

  showPrompts = false;
  promptVms: { def: SystemPromptDef; value: string }[] = [];
  promptsSaved = false;

  // ── Cluster de Cómputo ────────────────────────────────────────────────────
  activeSection: 'profile' | 'models' | 'cluster' | 'invitations' | 'projects' = 'profile';

  clusterUrl = '';
  clusterApiKey = '';
  clusterHasKey = false;
  clusterMaskedKey = '';
  clusterConfigLoading = false;
  clusterSaving = false;
  clusterSaved = false;
  clusterSaveError = '';

  clusterChecking = false;
  clusterCheckResult: import('../../task.models').ClusterHealthcheckResult | null = null;

  clusterMonitorOpen = false;
  clusterNodes: import('../../task.models').ClusterNodeInfo[] = [];
  clusterNodesLoading = false;
  clusterNodesError = '';
  clusterQueue: import('../../task.models').ClusterQueueEntry[] = [];
  clusterQueueLoading = false;
  clusterQueueError = '';
  private _clusterMonitorTimer: ReturnType<typeof setInterval> | null = null;
  // ─────────────────────────────────────────────────────────────────────────

  toast: { message: string; type: 'success' | 'warning' } | null = null;
  private _toastTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly taskService: TaskService,
    private readonly userPrefs: UserPreferencesService,
    private readonly cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.currentUserId = this.taskService.getCurrentUserIdFromToken();
    this.loadProfile();
    this.loadOwnedProjects();
    this.loadInvitations();
    this.loadModelSection();
    this.loadClusterConfig();
  }

  // ── Profile ───────────────────────────────────────────────────────────────

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
  }

  // ── Projects ──────────────────────────────────────────────────────────────

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

  private _buildContributorList(_p: ProjectDto): ContributorDto[] {
    return [];
  }

  toggleProject(vm: ProjectManageVm): void {
    vm.expanded = !vm.expanded;
    if (vm.expanded && !vm.contributorsLoaded) {
      this.taskService.getContributors(vm.project.id).subscribe({
        next: (res) => {
          vm.contributors = res.contributors || [];
          vm.contributorsLoaded = true;
          this.cdr.detectChanges();
        },
        error: () => {
          vm.contributorsLoaded = true;
          this.cdr.detectChanges();
        }
      });
    }
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
      next: (res: any) => {
        this.ownedProjects = this.ownedProjects.filter(v => v.project.id !== vm.project.id);
        const ghWarning: string | undefined = res?.github_warning;
        if (ghWarning) {
          this.showToast(`Proyecto "${vm.project.name}" eliminado del sistema. Aviso GitHub: ${ghWarning}`, 'warning');
        } else {
          this.showToast(`Proyecto "${vm.project.name}" eliminado del sistema y del repositorio de GitHub.`, 'success');
        }
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

  // ── IA & Modelos ──────────────────────────────────────────────────────────

  private loadModelSection(): void {
    if (!this.taskService.getAccessToken()) return;
    this.modelsLoading = true;
    this.defaultModelId = this.userPrefs.getDefaultModelId();

    // Build prompt VMs from stored values (or defaults)
    this.promptVms = DEFAULT_SYSTEM_PROMPTS.map(def => ({
      def,
      value: this.userPrefs.getSystemPrompt(def.key, def.defaultText),
    }));

    this.taskService.getAvailableModels().subscribe({
      next: models => {
        this.modelsLoading = false;
        this.modelVms = models.map(m => ({
          model: m,
          status: null,
          keyInput: '',
          saving: false,
          saved: false,
          error: '',
        }));
        this.cdr.detectChanges();
        // Load key status for each model
        for (const vm of this.modelVms) {
          this.taskService.getApiKeyStatus(vm.model.id).subscribe({
            next: status => { vm.status = status; this.cdr.detectChanges(); },
            error: () => { this.cdr.detectChanges(); },
          });
        }
      },
      error: () => {
        this.modelsLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  saveDefaultModel(): void {
    this.userPrefs.setDefaultModelId(this.defaultModelId);
    this.defaultModelSaved = true;
    setTimeout(() => { this.defaultModelSaved = false; this.cdr.detectChanges(); }, 2500);
    this.cdr.detectChanges();
  }

  saveModelKey(vm: ModelKeyVm): void {
    if (!vm.keyInput.trim()) return;
    vm.saving = true;
    vm.error = '';
    vm.saved = false;
    this.taskService.saveApiKey(vm.model.id, vm.keyInput).subscribe({
      next: status => {
        vm.status = status;
        vm.keyInput = '';
        vm.saving = false;
        vm.saved = true;
        setTimeout(() => { vm.saved = false; this.cdr.detectChanges(); }, 2500);
        this.cdr.detectChanges();
      },
      error: err => {
        vm.error = err?.error?.error ?? 'Error al guardar la clave.';
        vm.saving = false;
        this.cdr.detectChanges();
      },
    });
  }

  savePrompts(): void {
    for (const pvm of this.promptVms) {
      this.userPrefs.setSystemPrompt(pvm.def.key, pvm.value);
    }
    this.promptsSaved = true;
    setTimeout(() => { this.promptsSaved = false; this.cdr.detectChanges(); }, 2500);
    this.cdr.detectChanges();
  }

  resetPrompt(pvm: { def: SystemPromptDef; value: string }): void {
    this.userPrefs.resetSystemPrompt(pvm.def.key);
    pvm.value = pvm.def.defaultText;
    this.cdr.detectChanges();
  }

  // ── Cluster de Cómputo ────────────────────────────────────────────────────

  private loadClusterConfig(): void {
    if (!this.taskService.getAccessToken()) return;
    this.clusterConfigLoading = true;
    this.taskService.getClusterConfig().subscribe({
      next: cfg => {
        this.clusterUrl = cfg.url || '';
        this.clusterHasKey = cfg.has_key;
        this.clusterMaskedKey = cfg.masked_key || '';
        this.clusterConfigLoading = false;
        this.cdr.detectChanges();
      },
      error: () => { this.clusterConfigLoading = false; this.cdr.detectChanges(); },
    });
  }

  saveClusterConfig(): void {
    if (!this.clusterUrl.trim() && !this.clusterApiKey.trim()) return;
    this.clusterSaving = true;
    this.clusterSaveError = '';
    this.clusterSaved = false;
    this.taskService.saveClusterConfig(this.clusterUrl.trim(), this.clusterApiKey.trim()).subscribe({
      next: () => {
        if (this.clusterApiKey.trim()) {
          this.clusterHasKey = true;
          this.clusterMaskedKey = this.clusterApiKey.slice(0, 4) + '***...' + this.clusterApiKey.slice(-4);
          this.clusterApiKey = '';
        }
        this.clusterSaving = false;
        this.clusterSaved = true;
        setTimeout(() => { this.clusterSaved = false; this.cdr.detectChanges(); }, 2500);
        this.cdr.detectChanges();
      },
      error: err => {
        this.clusterSaveError = err?.error?.error ?? 'Error al guardar.';
        this.clusterSaving = false;
        this.cdr.detectChanges();
      },
    });
  }

  runClusterHealthcheck(): void {
    this.clusterChecking = true;
    this.clusterCheckResult = null;
    this.taskService.clusterHealthcheck(
      this.clusterUrl.trim() || undefined,
      this.clusterApiKey.trim() || undefined,
    ).subscribe({
      next: result => {
        this.clusterCheckResult = result;
        this.clusterChecking = false;
        this.cdr.detectChanges();
      },
      error: err => {
        this.clusterCheckResult = { ok: false, step: 'http', error: err?.error?.error ?? 'Error de red' };
        this.clusterChecking = false;
        this.cdr.detectChanges();
      },
    });
  }

  openClusterMonitor(): void {
    this.clusterMonitorOpen = true;
    this._refreshMonitor();
    this._clusterMonitorTimer = setInterval(() => this._refreshMonitor(), 5000);
  }

  closeClusterMonitor(): void {
    this.clusterMonitorOpen = false;
    if (this._clusterMonitorTimer !== null) {
      clearInterval(this._clusterMonitorTimer);
      this._clusterMonitorTimer = null;
    }
  }

  private _refreshMonitor(): void {
    this.clusterNodesLoading = true;
    this.clusterQueueLoading = true;
    this.taskService.clusterNodes().subscribe({
      next: res => {
        this.clusterNodes = res.nodes ?? [];
        this.clusterNodesError = '';
        this.clusterNodesLoading = false;
        this.cdr.detectChanges();
      },
      error: err => {
        this.clusterNodesError = err?.error?.error ?? 'Error al obtener nodos';
        this.clusterNodesLoading = false;
        this.cdr.detectChanges();
      },
    });
    this.taskService.clusterQueue().subscribe({
      next: res => {
        this.clusterQueue = res.jobs ?? [];
        this.clusterQueueError = '';
        this.clusterQueueLoading = false;
        this.cdr.detectChanges();
      },
      error: err => {
        this.clusterQueueError = err?.error?.error ?? 'Error al obtener cola';
        this.clusterQueueLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  // ── Toast ─────────────────────────────────────────────────────────────────

  showToast(message: string, type: 'success' | 'warning' = 'success'): void {
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this.toast = { message, type };
    this.cdr.detectChanges();
    this._toastTimer = setTimeout(() => {
      this.toast = null;
      this.cdr.detectChanges();
    }, 5000);
  }

  dismissToast(): void {
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this.toast = null;
    this.cdr.detectChanges();
  }

  ngOnDestroy(): void {
    if (this._clusterMonitorTimer !== null) {
      clearInterval(this._clusterMonitorTimer);
    }
    if (this._toastTimer !== null) {
      clearTimeout(this._toastTimer);
    }
  }
}

