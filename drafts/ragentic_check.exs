# Run Ragentic's own checks against every draft payload, from a ragentic checkout:
#
#     MIX_ENV=test mix run --no-start /path/to/manifests-catalog/drafts/ragentic_check.exs \
#       /path/to/manifests-catalog/drafts
#
# For each drafts/<app>/payload.json: sign it with a throwaway Ed25519 key generated
# in memory (never written anywhere, never the registry key), verify the bundle and a
# one-entry index with RagenticManifests.Trust, then load the A2UI setup surface,
# the credential declaration, OAuth provider, reviewed headers and probe, and validate
# the Connector and Credential manifests Registry.Persistence would create from it.
# Exit status 0 means every draft passed.

alias RagenticManifests.Trust
alias Ragentic.Connectors.Registry

alias Ragentic.Connectors.Registry.{
  ConnectionProbe,
  CredentialConfig,
  OAuth,
  RequestHeaders,
  Setup
}

[dir] = System.argv()

check = fn label, result ->
  if result in [true, :ok] or match?({:ok, _}, result),
    do: :ok,
    else: {:error, "#{label}: #{inspect(result, limit: 5)}"}
end

# The documents Registry.Persistence creates from a bundle: a Connector from
# spec.base (plus endpointHosts and a credential reference) and a Credential
# from setup.credential. A placeholder secret stands in for the user's.
validate = fn doc ->
  r = Ragentic.Manifests.Apply.validate(doc)
  if r.valid, do: :ok, else: r.errors
end

connector = fn base ->
  base = Map.take(base, ~w(type protocol endpoint endpointHosts specification headers))
  {:ok, endpoint} = RagenticManifests.Sources.HTTP.validate_url(base["endpoint"])

  %{
    "apiVersion" => "ragentic.io/v1",
    "kind" => "Connector",
    "metadata" => %{"namespace" => "default", "name" => "draft-check"},
    "spec" =>
      base
      |> Map.put_new("endpointHosts", [endpoint.host])
      |> Map.put("credential", %{"namespace" => "default", "name" => "draft-check-credential"})
  }
end

credential_doc = fn credential ->
  {type, config} =
    case credential do
      %{"type" => "oauth2_authorization_code" = type} ->
        {type, %{}}

      other ->
        with {:ok, %{type: t, config: c}} <- CredentialConfig.normalize(other),
             do: {Atom.to_string(t), c}
    end

  %{
    "apiVersion" => "ragentic.io/v1",
    "kind" => "Credential",
    "metadata" => %{"namespace" => "default", "name" => "draft-check-credential"},
    "spec" => Map.merge(config, %{"type" => type, "secret" => "placeholder"})
  }
end

drafts =
  dir
  |> Path.join("*/payload.json")
  |> Path.wildcard()
  |> Enum.sort()

results =
  for path <- drafts do
    payload = path |> File.read!() |> Jason.decode!()
    app = payload["app"]
    {public, private} = Trust.keypair()
    envelope = Trust.sign(payload, private)
    digest = Trust.digest(envelope)
    now = payload["not_before"] + 1

    index =
      Trust.sign(
        %{
          "kind" => "index",
          "registry" => "manifests.ragentic.io",
          "sequence" => 10,
          "not_before" => payload["not_before"],
          "expires" => payload["expires"],
          "entries" => [
            %{
              "id" => app,
              "title" => payload["manifest"]["spec"]["title"],
              "protocol" => payload["protocol"],
              "version" => payload["version"],
              "digest" => digest
            }
          ]
        },
        private
      )

    credential = get_in(payload, ["setup", "credential"])
    base = get_in(payload, ["manifest", "spec", "base"]) || %{}

    credential_check =
      case credential do
        %{"type" => "oauth2_authorization_code", "provider" => provider} ->
          OAuth.normalize(provider)

        other ->
          CredentialConfig.normalize(other)
      end

    errors =
      [
        check.(
          "bundle signature",
          Trust.verify(
            %{"chain" => [], "envelope" => envelope},
            public,
            %{app: app, version: payload["version"], digest: digest}, now: now)
        ),
        check.("index", Trust.verify_index(index, public, "manifests.ragentic.io", 10, now: now)),
        check.("connectable", Registry.connectable?(payload)),
        check.("setup surface", Setup.load(payload)),
        check.("credential", credential_check),
        check.("headers", RequestHeaders.normalize(base["headers"] || %{})),
        check.("probe", ConnectionProbe.check(get_in(payload, ["setup", "probe"]))),
        check.("connector manifest", validate.(connector.(base))),
        check.("credential manifest", validate.(credential_doc.(credential)))
      ]
      |> Enum.flat_map(fn
        :ok -> []
        {:error, message} -> [message]
      end)

    case errors do
      [] ->
        IO.puts("ok #{app}: signed #{byte_size(Jason.encode!(payload))} bytes, digest #{digest}")
        :ok

      errors ->
        IO.puts("FAIL #{app}: " <> Enum.join(errors, "; "))
        :error
    end
  end

failed = Enum.count(results, &(&1 == :error))

IO.puts(
  "#{length(results)} drafts checked by Ragentic: #{if failed == 0, do: "all passed", else: "#{failed} failed"}"
)

if failed > 0 or results == [], do: System.halt(1)
