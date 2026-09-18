import { createRoot } from 'react-dom/client';
import { Workspace } from './studio/Workspace';

// One application. Old bookmarks retain their character/job, not their old screen.
const query = new URLSearchParams(location.search);
for (const key of ['stage', 'view']) query.delete(key);
history.replaceState(null, '', `/${query.size ? `?${query}` : ''}`);
createRoot(document.getElementById('app')!).render(<Workspace />);
