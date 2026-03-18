import { Routes } from '@angular/router';
import { AuthPageComponent } from './pages/auth-page/auth-page';
import { ShellComponent } from './shell.component';
import { MenuPageComponent } from './pages/menu-page/menu-page';
import { ValidationPageComponent } from './pages/validation-page/validation-page';
import { TranslationPageComponent } from './pages/translation-page/translation-page';
import { ProofSearchPageComponent } from './pages/proof-search-page/proof-search-page';
import { LineageSearchPageComponent } from './pages/lineage-search-page/lineage-search-page';
import { CreateProjectPageComponent } from './pages/create-project-page/create-project-page';
import { ProjectSearchPageComponent } from './pages/project-search-page/project-search-page';
import { OpenWorkspacePageComponent } from './pages/open-workspace-page/open-workspace-page';
import { WorkspacePageComponent } from './pages/workspace-page/workspace-page';
import { AccountConfigPageComponent } from './pages/account-config-page/account-config-page';
import { EnvironmentConfigPageComponent } from './pages/environment-config-page/environment-config-page';
import { DebugExecutorsPageComponent } from './pages/debug-executors-page/debug-executors-page';

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
