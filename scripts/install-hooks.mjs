import { execFileSync } from 'node:child_process'
import { chmodSync } from 'node:fs'
// npm ci in Actions needs neither local hooks nor write access to Git configuration.
if (process.env.CI !== 'true') {
  const current = (() => {
    try { return execFileSync('git', ['config', '--get', 'core.hooksPath'], { encoding: 'utf8' }).trim() }
    catch (error) { if (error.status === 1) return ''; throw error }
  })()
  if (current && current !== '.githooks') throw new Error('Existing hooksPath detected; integrate privacy hooks before replacing it.')
  for (const hook of ['pre-commit', 'pre-push']) chmodSync(`.githooks/${hook}`, 0o755)
  execFileSync('git', ['config', '--local', 'core.hooksPath', '.githooks'])
  console.log('Privacy hooks installed. Python 3 and Gitleaks are required; checks fail closed.')
}
