import { Routes } from '@angular/router';
import { AuthPageComponent } from './pages/auth-page.component';
import { ShellComponent } from './shell.component';
import { MenuPageComponent } from './pages/menu-page.component';
import { ValidationPageComponent } from './pages/validation-page.component';
import { TranslationPageComponent } from './pages/translation-page.component';
import { ProofSearchPageComponent } from './pages/proof-search-page.component';
import { LineageSearchPageComponent } from './pages/lineage-search-page.component';
import { CreateProjectPageComponent } from './pages/create-project-page.component';
import { ProjectSearchPageComponent } from './pages/project-search-page.component';
import { OpenWorkspacePageComponent } from './pages/open-workspace-page.component';
import { WorkspacePageComponent } from './pages/workspace-page.component';
import { AccountConfigPageComponent } from './pages/account-config-page.component';
import { EnvironmentConfigPageComponent } from './pages/environment-config-page.component';
import { DebugExecutorsPageComponent } from './pages/debug-executors-page.component';

export const routes: Routes = [
	{ path: 'auth', component: AuthPageComponent },
	{
		path: '',
		component: ShellComponent,
		children: [
			{ path: 'menu', component: MenuPageComponent },
			{ path: 'validation', component: ValidationPageComponent },
			{ path: 'translation', component: TranslationPageComponent },
			{ path: 'proof-search', component: ProofSearchPageComponent },
			{ path: 'lineage-search', component: LineageSearchPageComponent },
			{ path: 'create-project', component: CreateProjectPageComponent },
			{ path: 'project-search', component: ProjectSearchPageComponent },
			{ path: 'open-workspace', component: OpenWorkspacePageComponent },
			{ path: 'workspace', component: WorkspacePageComponent },
			{ path: 'account-config', component: AccountConfigPageComponent },
			{ path: 'environment-config', component: EnvironmentConfigPageComponent },
			{ path: 'debug-executors', component: DebugExecutorsPageComponent },
			{ path: '', pathMatch: 'full', redirectTo: 'menu' }
		]
	},
	{ path: '**', redirectTo: 'auth' }
];
