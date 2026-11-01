# Sign the reviewed drafts and write the next catalog sequence. DJ runs this on a trusted
# machine, from a ragentic checkout; builders never run it with the real key.
#
#     REGISTRY_KEY_FILE=/secure/path/root.key mix run --no-start \
#       /path/to/manifests-catalog/drafts/publish.exs /path/to/manifests-catalog [OUT_DIR]
#
# REGISTRY_KEY_FILE holds the base64url (no padding) 32-byte Ed25519 private key of the
# registry root. The script refuses to sign unless its public key equals the pinned root
# below. `REGISTRY_KEY_FILE=ephemeral` signs with a throwaway in-memory key (dry run: the
# root check is skipped and nothing it writes can be trusted). OUT_DIR defaults to the
# catalog repository itself: bundles/<digest>.json are added, index.json is replaced.
#
# Environment, all optional: BASE_INDEX (path of the signed index to extend, verified
# against the root; default CATALOG_REPO/index.json), SEQUENCE (base + 1), NOT_BEFORE / EXPIRES (unix seconds; default:
# the index keeps the base index's expiry, not_before = now), APPS (comma list, default all
# drafts).

alias RagenticManifests.Trust

root = Base.url_decode64!("wFvL-3yCuZX52nrDbSxvTgeb5s4KFp6aS2W8JikogGs", padding: false)
registry = "manifests.ragentic.io"

{repo, out} =
  case System.argv() do
    [repo] -> {repo, repo}
    [repo, out] -> {repo, out}
    _ -> raise "usage: mix run --no-start drafts/publish.exs CATALOG_REPO [OUT_DIR]"
  end

int_env = fn name, default ->
  case System.get_env(name) do
    nil -> default
    value -> String.to_integer(value)
  end
end

{public, private, dry_run?} =
  case System.fetch_env!("REGISTRY_KEY_FILE") do
    "ephemeral" ->
      {pub, priv} = Trust.keypair()
      {pub, priv, true}

    path ->
      private = path |> File.read!() |> String.trim() |> Base.url_decode64!(padding: false)
      {pub, _} = :crypto.generate_key(:eddsa, :ed25519, private)
      if pub != root, do: raise("REGISTRY_KEY_FILE is not the pinned manifests.ragentic.io root")
      {pub, private, false}
  end

# The current index must verify against the pinned root before anything is added to it.
# BASE_INDEX is the newest signed index (production's, see PUBLISHING.md); without it,
# this repository's index.json.
current_envelope =
  (System.get_env("BASE_INDEX") || Path.join(repo, "index.json"))
  |> File.read!()
  |> Jason.decode!()

{:ok, current} =
  Trust.verify_index(current_envelope, root, registry, 0)

sequence = int_env.("SEQUENCE", current["sequence"] + 1)
if sequence <= current["sequence"], do: raise("SEQUENCE must exceed #{current["sequence"]}")
now = System.system_time(:second)
index_not_before = int_env.("NOT_BEFORE", now)
index_expires = int_env.("EXPIRES", current["expires"])

apps =
  case System.get_env("APPS") do
    nil -> nil
    list -> String.split(list, ",", trim: true)
  end

drafts =
  repo
  |> Path.join("drafts/*/payload.json")
  |> Path.wildcard()
  |> Enum.sort()
  |> Enum.map(&(&1 |> File.read!() |> Jason.decode!()))
  |> Enum.filter(&(apps == nil or &1["app"] in apps))

if drafts == [], do: raise("no drafts selected")
File.mkdir_p!(Path.join(out, "bundles"))

entries =
  for payload <- drafts do
    payload =
      payload
      |> Map.put("not_before", int_env.("NOT_BEFORE", payload["not_before"]))
      |> Map.put("expires", int_env.("EXPIRES", payload["expires"]))

    envelope = Trust.sign(payload, private)
    digest = Trust.digest(envelope)
    bundle = %{"chain" => [], "envelope" => envelope}
    check_at = max(now, payload["not_before"]) + 1

    {:ok, _} =
      Trust.verify(
        bundle,
        public,
        %{app: payload["app"], version: payload["version"], digest: digest}, now: check_at)

    File.write!(Path.join([out, "bundles", digest <> ".json"]), Jason.encode!(bundle))
    IO.puts("bundle #{payload["app"]} #{payload["version"]} #{digest}")

    %{
      "id" => payload["app"],
      "title" => payload["manifest"]["spec"]["title"],
      "protocol" => payload["protocol"],
      "version" => payload["version"],
      "digest" => digest
    }
  end

new_ids = MapSet.new(entries, & &1["id"])
kept = Enum.reject(current["entries"], &(&1["id"] in new_ids))

index =
  Trust.sign(
    %{
      "kind" => "index",
      "registry" => registry,
      "sequence" => sequence,
      "not_before" => index_not_before,
      "expires" => index_expires,
      "entries" => kept ++ entries
    },
    private
  )

{:ok, signed} =
  Trust.verify_index(index, public, registry, sequence, now: max(now, index_not_before) + 1)

File.write!(Path.join(out, "index.json"), Jason.encode!(index))

IO.puts(
  "index #{registry} sequence #{signed["sequence"]}: #{length(signed["entries"])} entries, " <>
    "expires #{DateTime.from_unix!(signed["expires"])}" <>
    if(dry_run?, do: " (EPHEMERAL KEY: dry run, not trusted)", else: "")
)
