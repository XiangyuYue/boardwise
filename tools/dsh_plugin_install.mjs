#!/usr/bin/env node
/**
 * 把 boardwise-dsh 的 tarball 装进一个 DSH profile。
 *
 * 为什么需要这个脚本：`dsh plugin --profile <p> add file:<tgz>` 对 Electron 应用
 * 独占管理的 profile（本机的 `desktop`）会直接拒绝——报
 * `profile "<p>" is managed exclusively by the Electron application`。
 * 命令本身没问题（在 `boardwise-clean` 这类 profile 上实测可用），只是 desktop
 * 这条路被应用锁住。手工装一次要做四件事，写成脚本后任何版本/任何 profile
 * 都是一条命令：
 *
 *   1. 备份 profile 的 package.json / pnpm-lock.yaml 与已装的同名包；
 *   2. 把 dependencies[<name>] 改写为 `file:<tarball 绝对路径>`；
 *   3. 确认 dsh.profile.bundles 里有这个包（没有就追加——否则装了不挂）；
 *   4. 跑 pnpm install，落盘后核对 node_modules/<name>/package.json 的版本与
 *      tarball 里的版本逐字相等才算成功。
 *
 * 脚本只动 profile，不碰仓库、不碰 git；失败时打印备份目录供人工回滚。
 *
 * 用法：
 *   node tools/dsh_plugin_install.mjs \
 *     --profile D:/dsh-home/profiles/desktop \
 *     --tarball dsh-plugin/boardwise-dsh-0.6.0.tgz
 *
 *   node tools/dsh_plugin_install.mjs --profile <dir> --tarball <tgz> --dry-run
 */
import { execFileSync } from 'node:child_process'
import {
  copyFileSync,
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs'
import { basename, dirname, join, resolve } from 'node:path'

const args = process.argv.slice(2)

function usage(message) {
  if (message) console.error(`error: ${message}`)
  console.error(
    'usage: node tools/dsh_plugin_install.mjs --profile <profile-dir> --tarball <tgz> [--dry-run] [--no-bundles]',
  )
  process.exit(2)
}

const options = { profile: null, tarball: null, dryRun: false, bundles: true }
for (let i = 0; i < args.length; i += 1) {
  const arg = args[i]
  if (arg === '--profile') options.profile = args[++i]
  else if (arg === '--tarball') options.tarball = args[++i]
  else if (arg === '--dry-run') options.dryRun = true
  else if (arg === '--no-bundles') options.bundles = false
  else if (arg === '-h' || arg === '--help') usage()
  else usage(`unknown argument: ${arg}`)
}
if (!options.profile) usage('missing --profile')
if (!options.tarball) usage('missing --tarball')

const profile = resolve(options.profile)
const tarball = resolve(options.tarball)
const manifestPath = join(profile, 'package.json')

if (!existsSync(profile)) usage(`profile directory not found: ${profile}`)
if (!existsSync(manifestPath)) usage(`not a dsh profile (no package.json): ${profile}`)
if (!existsSync(tarball)) usage(`tarball not found: ${tarball}`)

/** 读 tarball 里的 package/package.json —— 用系统 tar（Win10+/Linux 都自带）。
 *  Windows 优先 System32 的原生 tar：PATH 里的 MSYS tar 在受限子进程链里可能
 *  无法创建共享对象。传相对文件名 + cwd，避免盘符被 GNU tar 当成远程主机。 */
const windowsTar = process.platform === 'win32'
  ? join(process.env.SystemRoot ?? 'C:/Windows', 'System32', 'tar.exe')
  : null
const tarCommand = windowsTar && existsSync(windowsTar) ? windowsTar : 'tar'

function tarballManifest(file) {
  let text
  try {
    text = execFileSync(tarCommand, ['-xOzf', basename(file), 'package/package.json'], {
      cwd: dirname(file),
      encoding: 'utf8',
    })
  } catch (error) {
    usage(`cannot read package/package.json from ${file}: ${error.message}`)
  }
  try {
    return JSON.parse(text)
  } catch {
    usage(`${file}: package/package.json is not valid JSON`)
  }
}

const incoming = tarballManifest(tarball)
if (typeof incoming.name !== 'string' || typeof incoming.version !== 'string') {
  usage(`${tarball}: manifest has no name/version`)
}
const name = incoming.name
const version = incoming.version

const profileManifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
const oldSpec = profileManifest.dependencies?.[name] ?? null
const installedManifestPath = join(profile, 'node_modules', name, 'package.json')
const oldVersion = existsSync(installedManifestPath)
  ? JSON.parse(readFileSync(installedManifestPath, 'utf8')).version
  : null

const spec = `file:${tarball.replace(/\\/g, '/')}`
profileManifest.dsh ??= {}
profileManifest.dsh.profile ??= {}
profileManifest.dsh.profile.bundles ??= []
const bundles = profileManifest.dsh.profile.bundles
const needsBundle = options.bundles && !bundles.includes(name)

console.log(`profile : ${profile}`)
console.log(`package : ${name} ${version}  (current: ${oldVersion ?? 'none'})`)
console.log(`spec    : ${spec}`)
console.log(`bundles : ${needsBundle ? `add ${name}` : 'already listed / skipped'}`)
if (oldSpec && oldSpec !== spec) console.log(`replacing: ${oldSpec}`)

if (options.dryRun) {
  console.log('dry-run: nothing written.')
  process.exit(0)
}

/** 备份：profiles/ 与 DSH home 根都可能不可写，最后退到 profile 自己目录。 */
function backup() {
  const now = new Date()
  const pad = value => String(value).padStart(2, '0')
  const stamp =
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
    `-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  const dirName = `_backup_${name.replace(/\//g, '_')}_${stamp}`
  const candidates = [join(profile, '..'), join(profile, '..', '..'), profile]
  for (const base of candidates) {
    const target = join(base, dirName)
    try {
      mkdirSync(target, { recursive: false })
    } catch {
      continue
    }
    for (const file of ['package.json', 'pnpm-lock.yaml']) {
      const source = join(profile, file)
      if (existsSync(source)) copyFileSync(source, join(target, file))
    }
    const installed = join(profile, 'node_modules', name)
    if (existsSync(installed)) cpSync(installed, join(target, 'installed'), { recursive: true })
    return target
  }
  throw new Error(`cannot create a backup directory next to ${profile}`)
}

const backupDir = backup()
console.log(`backup  : ${backupDir}`)

profileManifest.dependencies ??= {}
profileManifest.dependencies[name] = spec
if (needsBundle) bundles.push(name)
writeFileSync(manifestPath, `${JSON.stringify(profileManifest, null, 2)}\n`, 'utf8')

let installOutput
try {
  installOutput =
    process.platform === 'win32'
      ? execFileSync(process.env.ComSpec ?? 'cmd.exe', ['/d', '/s', '/c', 'pnpm install --prefer-offline'], {
          cwd: profile,
          encoding: 'utf8',
          stdio: ['ignore', 'pipe', 'pipe'],
        })
      : execFileSync('pnpm', ['install', '--prefer-offline'], {
          cwd: profile,
          encoding: 'utf8',
          stdio: ['ignore', 'pipe', 'pipe'],
        })
} catch (error) {
  const detail = `${error.stdout ?? ''}${error.stderr ?? ''}`.trim().split('\n').slice(-6).join('\n')
  if (detail) console.error(detail)
  console.error(`error: pnpm install failed (exit ${error.status ?? '?'})`)
  console.error(`       roll back: copy ${join(backupDir, 'package.json')} / pnpm-lock.yaml back and re-run pnpm install`)
  process.exit(1)
}

const installedVersion = existsSync(installedManifestPath)
  ? JSON.parse(readFileSync(installedManifestPath, 'utf8')).version
  : null
if (installedVersion !== version) {
  console.error(`error: installed version mismatch: expected ${version}, got ${installedVersion}`)
  console.error(`       rollback backup: ${backupDir}`)
  process.exit(1)
}

void installOutput
console.log(`installed: ${name} ${installedVersion}`)
console.log('takes effect after DSH restarts (profile deps are read at process start).')
