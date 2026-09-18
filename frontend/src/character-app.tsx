import { createRoot } from 'react-dom/client';
import { CharacterFactory } from './factory/CharacterFactory';

// One application. Old bookmarks retain their character/job, not their old screen.
const query = new URLSearchParams(location.search);
for (const key of ['stage', 'view', 'tab']) query.delete(key);
history.replaceState(null, '', `/${query.size ? `?${query}` : ''}`);
createRoot(document.getElementById('app')!).render(<CharacterFactory />);
