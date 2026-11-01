# Deploys the newest signed catalog on main to the registry server's volume.
#
# Runs inside the ragentic-manifests image (`ragentic_manifests eval`), so the
# candidate is checked by the same code that serves it: if the server would not
# load it, nothing changes. Trust comes from MANIFESTS_ROOT_PUBLIC_KEY, never
# from the repository.
repo = System.get_env("SYNC_REPOSITORY", "ragentic-io/manifests-catalog")
branch = System.get_env("SYNC_BRANCH", "main")
catalog = Application.fetch_env!(:ragentic_manifests, :catalog_dir)
# Staged on the same volume so the swap is a rename, never a partial copy.
work = Path.join(catalog, ".sync")
files = ~w(index.json browse-index.json bundles browse-bundles)
marker = Path.join(catalog, ".synced-commit")

log = fn msg -> IO.puts("[sync] #{msg}") end
{:ok, _} = Application.ensure_all_started(:req)

sha =
  Req.get!("https://api.github.com/repos/#{repo}/commits/#{branch}",
    headers: [accept: "application/vnd.github.sha"],
    decode_body: false
  ).body
  |> String.trim()

unless sha =~ ~r/\A[0-9a-f]{40}\z/, do: raise("unexpected commit id #{inspect(sha)}")

if File.read(marker) == {:ok, sha} do
  log.("#{sha} is already deployed")
  System.halt(0)
end

File.rm_rf!(work)
stage = Path.join(work, "catalog")
File.mkdir_p!(stage)
tarball = Path.join(work, "catalog.tar.gz")

Req.get!("https://codeload.github.com/#{repo}/tar.gz/#{sha}", into: File.stream!(tarball), retry: :transient)

{_, 0} =
  System.cmd("tar", [
    "-xzf", tarball, "-C", stage, "--strip-components=1", "--wildcards",
    "*/index.json", "*/browse-index.json", "*/bundles/*", "*/browse-bundles/*"
  ])

File.rm!(tarball)

# Load the candidate exactly as the server would.
Application.put_env(:ragentic_manifests, :catalog_dir, stage)

case RagenticManifests.Browse.search(%{}) do
  %{} = page ->
    log.("#{sha} verified: #{inspect(Map.get(page, :total))} applications")

  other ->
    log.("#{sha} rejected by the server's checks: #{inspect(other)}; keeping the current catalog")
    System.halt(1)
end

previous = Path.join(catalog, ".previous")
File.rm_rf!(previous)
File.mkdir_p!(previous)

for f <- files, File.exists?(Path.join(catalog, f)) do
  File.rename!(Path.join(catalog, f), Path.join(previous, f))
end

for f <- files, do: File.rename!(Path.join(stage, f), Path.join(catalog, f))

File.write!(marker, sha)
File.rm_rf!(work)
log.("deployed #{sha}; the previous catalog is in #{previous}")
