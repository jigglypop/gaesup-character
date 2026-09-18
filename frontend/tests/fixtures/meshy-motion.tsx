import { createRoot } from 'react-dom/client';
import { MeshyMotion } from '../../src/factory/MeshyMotion';

createRoot(document.getElementById('root')!).render(<MeshyMotion jobId={'c'.repeat(24)} />);
