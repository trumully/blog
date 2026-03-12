---
title: OAuth in a Multi-Revit-Version Add-in
date: 2026-03-12T04:31:01Z
description: A non-ideal solution to a particularly messy problem
tags: ["revit", "msal", "authentication", "csharp", "dotnet"]
---

Recently I've been working on an internal Revit add-in that runs lengthy pipelines with various database operations. These SQL executions require authentication, so MSAL was a natural choice to handle this. However, working on an add-in supporting Revit 2023, 2024, and 2025 is a nuisance. Because you need to support .NET Framework 4.8 and .NET 8 all while sharing an assembly load context with Revit itself, you find yourself knee-deep in DLL Hell. Michael Shpilt covers this problem well in their [blog post](https://michaelscodingspot.com/dotnet-dll-hell/). In my case, I decided to use [IL-Repack](https://github.com/gluck/il-repack) to merge dependencies into a single DLL. You would assume this is enough — it is not. We have Dynamo to thank for that.

Revit loads all add-ins into a single Application Domain on .NET Framework 4.8 for Revit 2023/2024 and the default [`AssemblyLoadContext`](https://learn.microsoft.com/en-us/dotnet/core/dependency-loading/understanding-assemblyloadcontext) on .NET 8 for Revit 2025. Only one version of a given assembly can be active at a time. Dynamo, bundled with Revit, adds to the pile with its own pinned dependencies. MSAL and its transitive dependencies — including `Microsoft.Extensions.*`, `System.*`, and Windows Authentication Manager (an out-of-process OS-level broker with non-managed binaries) — are large and version-sensitive. In a shared loader context, any version conflict with Dynamo or another add-in may cause runtime failures that are difficult to diagnose and impossible to isolate. IL-merging MSAL unfortunately cannot prevent conflicts if the host or another add-in has already loaded a different version of an assembly into the same context.

My solution was a custom PKCE implementation built on [`TcpListener`](https://learn.microsoft.com/en-us/dotnet/api/system.net.sockets.tcplistener?view=net-8.0) and [`HttpClient`](https://learn.microsoft.com/en-us/dotnet/api/system.net.http.httpclient?view=net-8.0). These are stable and low-level .NET primitives. This means no additional managed dependencies and allows multi-target support of .NET Framework 4.8 and .NET 8.

The flow opens a loopback port with `TcpListener`, launches the system browser for the Entra ID authorization redirect, then exchanges the returned code for tokens via `HttpClient`.

## The flow in detail

**1. Claim a loopback port**

Binding `TcpListener` to port 0 lets the OS pick a free port. The port number is recorded and the temporary listener is stopped immediately. That port becomes the redirect URI for the session.

`HttpListener` would be the obvious choice, but on Windows it requires a URL ACL reservation or an elevated process. `TcpListener` doesn't, which matters when you don't control the host process.

**2. Generate the PKCE pair**

[Proof Key for Code Exchange](https://oauth.net/2/pkce/) (PKCE) prevents an authorization code from being redeemed by anything other than the client that requested it. A random 64-byte verifier is generated along with a SHA-256 challenge derived from it:

```csharp
string codeVerifier  = CreateCryptoRandomUrlSafe(64);       // random bytes → base64url
string codeChallenge = CreateCodeChallenge(codeVerifier);   // SHA-256(verifier) → base64url
```

The verifier is sent later at token exchange. The challenge is sent up front with the authorization request. Entra stores the challenge and verifies the verifier matches when the code is redeemed.

A random `state` value is generated the same way and round-tripped through the redirect to guard against [Cross Site Request Forgery](https://owasp.org/www-community/attacks/csrf) (CSRF).

**3. Start the listener**

The loopback server is started before [`Process.Start`](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.start?view=net-8.0) launches the browser. If you open the browser first, the authorization redirect can beat your listener on a fast machine and the connection is refused.

**4. Open the browser and wait**

`Process.Start` with `UseShellExecute = true` hands the URL to the OS, which opens the default browser. The browser isn't closed afterward.

A `TaskCompletionSource` bridges the listener and the calling code. The main flow awaits it with a 5-minute timeout and the listener signals it once a valid code arrives.

**5. Parse the callback and validate state**

When the browser follows the redirect, the loopback server reads the raw HTTP request line and extracts `code`, `state`, and `error` from the query string. If the state doesn't match what was sent, the flow is aborted. The TCS is signalled _before_ writing the HTTP response, so the token exchange starts while the browser is still receiving the page.

**6. Exchange the code for tokens**

A standard `application/x-www-form-urlencoded` POST to the v2.0 token endpoint with `grant_type=authorization_code` and the `code_verifier`. The response is a `TokenResponse` with an access token, refresh token, and expiry.

In Revit's restricted execution environment, constructing a new `HttpClient` per-request can throw a `MethodAccessException`. Declaring the `HttpClient` as `static` avoids this.

**7. Token caching and silent refresh**

`AcquireTokenInteractive` should only be called once. After that, `EnsureTokenFresh` handles everything: it returns the cached token if it has more than 20 minutes left, or does a silent refresh via the refresh token if not. The 20-minute buffer is there to account for clock skew and latency.

A `SemaphoreSlim(1,1)` ensures only one thread hits the token endpoint at a time. A plain `object` lock guards the cached values for synchronous reads. The two locks are kept separate to avoid deadlocking Revit's dispatcher thread when `EnsureTokenFresh` is called from UI code.

## Usage in a Revit command

Each `IExternalCommand` calls `EntraPkceAuth.AcquireTokenInteractive` at the top of `Execute`. The first time it opens the browser and waits for the user to sign in. After that, the cached token is returned straight away.

```csharp
[Transaction(TransactionMode.Manual)]
public class MyCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        EntraPkceAuth.AcquireTokenInteractive();

        var result = SyncPipeline.Execute(commandData);
        message = result.Message;
        return result.IsSuccess ? Result.Succeeded : Result.Failed;
    }
}
```

SQL connections use a `SqlAuthenticationProvider` callback to get a fresh token each time a connection is opened:

```csharp
public class DataRepository
{
    public SqlConnection Connection { get; } = new(connectionString);

    private static async Task<SqlAuthenticationToken> AccessTokenCallback(
        SqlAuthenticationParameters authParams,
        CancellationToken cancellationToken
    )
    {
        var (accessToken, expiresOn) = await EntraPkceAuth
            .EnsureTokenFreshAsync(cancellationToken)
            .ConfigureAwait(false);
        return new SqlAuthenticationToken(accessToken, expiresOn);
    }
}
```

`EnsureTokenFreshAsync` returns straight away if the token has more than 20 minutes left, so the callback doesn't add noticeable latency on connection opens.

This is important because some commands run for a long time and a user is not going to sit and stare at their screen for a full hour waiting for a browser pop-up. `AcquireTokenInteractive` at the start of `Execute` makes sure the user is signed in before anything runs, but the callback handles the rest by refreshing the token on each connection open.

<details>
<summary>Full implementation — <code>EntraPkceAuth.cs</code></summary>

```csharp
using System.Diagnostics;
using System.Net;
#pragma warning disable IDE0005 // Using directive is unnecessary.
using System.Net.Http;
#pragma warning restore IDE0005 // Using directive is unnecessary.
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

public sealed class TokenResponse
{
    [JsonPropertyName("access_token")]
    public string AccessToken { get; set; } = "";

    [JsonPropertyName("token_type")]
    public string TokenType { get; set; } = "";

    [JsonPropertyName("expires_in")]
    public int ExpiresIn { get; set; }

    [JsonPropertyName("scope")]
    public string Scope { get; set; } = "";

    [JsonPropertyName("refresh_token")]
    public string RefreshToken { get; set; } = "";

    [JsonPropertyName("id_token")]
    public string IdToken { get; set; } = "";
}

public static class EntraPkceAuth
{
    private const string TenantId = "xxx-xxx-xxx";

    // Well-known ADO.NET / SqlClient public client ID — safe to keep as default
    // https://github.com/dotnet/SqlClient/blob/77c35d86c641cd12b6562d86e7bb4bd7a689b336/src/Microsoft.Data.SqlClient/src/Microsoft/Data/SqlClient/TdsEnums.cs#L1185
    private const string ClientId = "2fd908ad-0664-4344-b9be-cd3e8b574c38";

    // Azure SQL scope
    private const string Scope = "https://database.windows.net/.default";

    // Refresh the token this many minutes before it expires to avoid clock skew and latency
    private const int TokenRefreshBufferMinutes = 20;

    private static TokenResponse? _cachedToken;
    private static DateTimeOffset _tokenExpiresOn;
    private static readonly object _cacheLock = new();

    // static HttpClient to avoid MethodAccessException in restricted environments
    private static readonly HttpClient _httpClient = new HttpClient();
    private static readonly SemaphoreSlim _authLock = new(1, 1);

    public static TokenResponse AcquireTokenInteractive(CancellationToken ct = default)
    {
        return AcquireTokenInteractiveAsync(ct).GetAwaiter().GetResult();
    }

    /// <summary>
    /// Returns a valid access token and its expiry, silently refreshing if the token will expire
    /// within a configured buffer window before expiry (see <see cref="TokenRefreshBufferMinutes"/>).
    /// Never opens a browser. Throws <see cref="InvalidOperationException"/> if the token cannot be
    /// refreshed silently (e.g. no refresh token, or refresh token has expired). Other exceptions
    /// from underlying operations (e.g. <see cref="HttpRequestException"/> on network
    /// errors or <see cref="OperationCanceledException"/> on cancellation) may also propagate.
    /// </summary>
    public static (string AccessToken, DateTimeOffset ExpiresOn) EnsureTokenFresh(CancellationToken ct = default)
    {
        return EnsureTokenFreshAsync(ct).GetAwaiter().GetResult();
    }

    /// <inheritdoc cref="EnsureTokenFresh"/>
    public static async Task<(string AccessToken, DateTimeOffset ExpiresOn)> EnsureTokenFreshAsync(
        CancellationToken ct = default
    )
    {
        if (TryGetCachedToken(out var accessToken, out var expiresOn))
        {
            return (accessToken, expiresOn);
        }

        await _authLock.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            if (TryGetCachedToken(out accessToken, out expiresOn))
            {
                return (accessToken, expiresOn);
            }

            string? refreshToken = GetRefreshToken();

            if (!string.IsNullOrEmpty(refreshToken))
            {
                try
                {
                    var refreshed = await RefreshTokenAsync(refreshToken!, ct).ConfigureAwait(false);
                    UpdateCache(refreshed);
                    return (refreshed.AccessToken, _tokenExpiresOn);
                }
                catch (InvalidOperationException ex)
                {
                    ClearCache();
                    throw new InvalidOperationException(
                        "Silent token refresh failed. Interactive authentication is required.",
                        ex
                    );
                }
                catch (HttpRequestException)
                {
                    // Transient network/server failure. If the token is still unexpired, return it
                    // rather than propagating and failing DB auth unnecessarily.
                    lock (_cacheLock)
                    {
                        if (_cachedToken is not null && _tokenExpiresOn > DateTimeOffset.UtcNow)
                        {
                            return (_cachedToken.AccessToken, _tokenExpiresOn);
                        }
                    }
                    throw;
                }
            }

            throw new InvalidOperationException(
                _cachedToken is null
                    ? "No cached token available. Interactive authentication is required."
                    : "No refresh token available for silent refresh. Interactive authentication is required."
            );
        }
        finally
        {
            _authLock.Release();
        }
    }

    public static async Task<TokenResponse> AcquireTokenInteractiveAsync(CancellationToken ct = default)
    {
        if (TryGetCachedTokenResponse(out var cached))
        {
            return cached;
        }

        await _authLock.WaitAsync(ct).ConfigureAwait(false);
        try
        {
            if (TryGetCachedTokenResponse(out cached))
            {
                return cached;
            }

            // Try refresh first
            string? refreshToken = GetRefreshToken();
            if (refreshToken is not null)
            {
                try
                {
                    var refreshedToken = await RefreshTokenAsync(refreshToken, ct).ConfigureAwait(false);
                    UpdateCache(refreshedToken);
                    return refreshedToken;
                }
                catch (InvalidOperationException)
                {
                    // Refresh token is invalid or expired; clear cache and fall back to interactive auth.
                    ClearCache();
                }
                catch (HttpRequestException)
                {
                    // Transient network/server failure during refresh. If the cached token is still
                    // unexpired, return it instead of forcing interactive auth.
                    lock (_cacheLock)
                    {
                        if (_cachedToken is not null && _tokenExpiresOn > DateTimeOffset.UtcNow)
                        {
                            return _cachedToken;
                        }
                    }
                    // No usable cached token; clear cache and fall back to interactive auth.
                    ClearCache();
                }
            }

            // 1) Pick a free localhost port for loopback
            int port = GetFreeTcpPort();
            string redirectUri = $"http://localhost:{port}/";

            // 2) Generate PKCE
            string codeVerifier = CreateCodeVerifier();
            string codeChallenge = CreateCodeChallenge(codeVerifier);
            string state = CreateCryptoRandomUrlSafe(32);

            // 3) Build authorize URL (v2.0 endpoint)
            string authorizeEndpoint = $"https://login.microsoftonline.com/{TenantId}/oauth2/v2.0/authorize";
            var authParams = new Dictionary<string, string>
            {
                ["client_id"] = ClientId,
                ["response_type"] = "code",
                ["response_mode"] = "query",
                ["redirect_uri"] = redirectUri,
                ["scope"] = Scope,
                ["state"] = state,
                ["code_challenge"] = codeChallenge,
                ["code_challenge_method"] = "S256",
                ["prompt"] = "select_account",
            };
            string authorizeUrl =
                authorizeEndpoint
                + "?"
                + string.Join(
                    "&",
                    authParams.Select(kvp => $"{WebUtility.UrlEncode(kvp.Key)}={WebUtility.UrlEncode(kvp.Value)}")
                );

            // 4) Start loopback HTTP listener
            using var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            var authCodeTcs = new TaskCompletionSource<(string code, string returnedState)>(
                TaskCreationOptions.RunContinuationsAsynchronously
            );
            var serverTask = RunLoopbackServerAsync(port, state, authCodeTcs, cts.Token);
            _ = serverTask.ContinueWith(
                t => authCodeTcs.TrySetException(t.Exception!.InnerExceptions),
                TaskContinuationOptions.OnlyOnFaulted
            );

            // 5) Open system default browser (MSAL behavior). We do not attempt to close it.
            OpenBrowser(authorizeUrl);

            // 6) Wait for the authorization response
            (string code, string returnedState) result;
            try
            {
#if NET8_0_OR_GREATER
                result = await authCodeTcs.Task.WaitAsync(TimeSpan.FromMinutes(5), ct).ConfigureAwait(false);
#else
                using var timeoutCts = new CancellationTokenSource(TimeSpan.FromMinutes(5));
                using var linkedCts = CancellationTokenSource.CreateLinkedTokenSource(ct, timeoutCts.Token);
                var completedTask = await Task.WhenAny(authCodeTcs.Task, Task.Delay(-1, linkedCts.Token))
                    .ConfigureAwait(false);
                if (completedTask != authCodeTcs.Task)
                {
                    ct.ThrowIfCancellationRequested();
                    throw new TimeoutException("The authentication operation timed out.");
                }
                result = await authCodeTcs.Task.ConfigureAwait(false);
#endif
            }
            finally
            {
                // Stop server
#if NET8_0_OR_GREATER
                await cts.CancelAsync().ConfigureAwait(false);
#else
                cts.Cancel();
#endif
            }

            if (result.returnedState != state)
            {
                throw new InvalidOperationException("State mismatch.");
            }

            // 7) Redeem code for tokens
            var token = await RedeemCodeForTokensAsync(result.code, redirectUri, codeVerifier, ct)
                .ConfigureAwait(false);

            UpdateCache(token);
            return token;
        }
        finally
        {
            _authLock.Release();
        }
    }

    public static DateTimeOffset TokenExpiry
    {
        get
        {
            lock (_cacheLock)
            {
                return _tokenExpiresOn;
            }
        }
    }

    private static bool TryGetCachedToken(out string accessToken, out DateTimeOffset expiresOn)
    {
        lock (_cacheLock)
        {
            if (
                _cachedToken is not null
                && _tokenExpiresOn > DateTimeOffset.UtcNow.AddMinutes(TokenRefreshBufferMinutes)
            )
            {
                accessToken = _cachedToken.AccessToken;
                expiresOn = _tokenExpiresOn;
                return true;
            }
        }
        accessToken = "";
        expiresOn = DateTimeOffset.MinValue;
        return false;
    }

    private static bool TryGetCachedTokenResponse(out TokenResponse token)
    {
        lock (_cacheLock)
        {
            if (
                _cachedToken is not null
                && _tokenExpiresOn > DateTimeOffset.UtcNow.AddMinutes(TokenRefreshBufferMinutes)
            )
            {
                token = _cachedToken;
                return true;
            }
        }
        token = null!;
        return false;
    }

    private static string? GetRefreshToken() { lock (_cacheLock) return _cachedToken?.RefreshToken; }

    private static void UpdateCache(TokenResponse token)
    {
        lock (_cacheLock)
        {
            _cachedToken = token;
            _tokenExpiresOn = DateTimeOffset.UtcNow.AddSeconds(token.ExpiresIn);
        }
    }

    private static void ClearCache()
    {
        lock (_cacheLock)
        {
            _cachedToken = null;
            _tokenExpiresOn = DateTimeOffset.MinValue;
        }
    }

    private static async Task<TokenResponse> RefreshTokenAsync(string refreshToken, CancellationToken ct = default)
    {
        var tokenEndpoint = new Uri($"https://login.microsoftonline.com/{TenantId}/oauth2/v2.0/token");

        var form = new Dictionary<string, string>
        {
            ["client_id"] = ClientId,
            ["grant_type"] = "refresh_token",
            ["refresh_token"] = refreshToken,
            ["scope"] = Scope,
        };
        using var encodedForm = new FormUrlEncodedContent(form);
        using var resp = await _httpClient.PostAsync(tokenEndpoint, encodedForm, ct).ConfigureAwait(false);
#if NET8_0_OR_GREATER
        string json = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
#else
        string json = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
#endif
        if (!resp.IsSuccessStatusCode)
        {
            // A 400 with invalid_grant or interaction_required means the refresh token is expired
            // or revoked — interactive re-authentication is the only recovery path. All other
            // failures (rate limiting, server errors, etc.) are transient; throw HttpRequestException
            // so callers can distinguish them from permanent auth failures.
            if (resp.StatusCode == HttpStatusCode.BadRequest && IsInteractiveAuthRequired(json))
            {
                throw new InvalidOperationException(
                    $"Token refresh failed: {(int)resp.StatusCode} {resp.ReasonPhrase}\n{json}"
                );
            }
            throw new HttpRequestException($"Token refresh failed: {(int)resp.StatusCode} {resp.ReasonPhrase}\n{json}");
        }
        var tokenResponse =
            JsonSerializer.Deserialize<TokenResponse>(json)
            ?? throw new InvalidOperationException($"Failed to deserialize token response. Raw JSON: {json}");
        return tokenResponse;
    }

    private static bool IsInteractiveAuthRequired(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            if (!doc.RootElement.TryGetProperty("error", out var errorProp))
            {
                return false;
            }

            var error = errorProp.GetString();
            return error is "invalid_grant" or "interaction_required";
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static async Task<TokenResponse> RedeemCodeForTokensAsync(
        string code,
        string redirectUri,
        string codeVerifier,
        CancellationToken ct
    )
    {
        var tokenEndpoint = new Uri($"https://login.microsoftonline.com/{TenantId}/oauth2/v2.0/token");

        var form = new Dictionary<string, string>
        {
            ["client_id"] = ClientId,
            ["grant_type"] = "authorization_code",
            ["code"] = code,
            ["redirect_uri"] = redirectUri,
            ["code_verifier"] = codeVerifier,
            ["scope"] = Scope,
        };
        using var encodedForm = new FormUrlEncodedContent(form);
        using var resp = await _httpClient.PostAsync(tokenEndpoint, encodedForm, ct).ConfigureAwait(false);
#if NET8_0_OR_GREATER
        string json = await resp.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
#else
        string json = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
#endif
        if (!resp.IsSuccessStatusCode)
        {
            throw new InvalidOperationException(
                $"Token exchange failed: {(int)resp.StatusCode} {resp.ReasonPhrase}\n{json}"
            );
        }
        var tokenResponse =
            JsonSerializer.Deserialize<TokenResponse>(json)
            ?? throw new InvalidOperationException($"Failed to deserialize token response. Raw JSON: {json}");
        return tokenResponse;
    }

    private static async Task RunLoopbackServerAsync(
        int port,
        string expectedState,
        TaskCompletionSource<(string code, string state)> tcs,
        CancellationToken ct
    )
    {
#if NET8_0_OR_GREATER
        using var listener = new TcpListener(IPAddress.Loopback, port);
#else
        var listener = new TcpListener(IPAddress.Loopback, port);
#endif
        listener.Start();
        try
        {
            TcpClient client;
#if NET8_0_OR_GREATER
            try
            {
                client = await listener.AcceptTcpClientAsync(ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return;
            }
#else
            using (ct.Register(listener.Stop))
            {
                try
                {
                    client = await listener.AcceptTcpClientAsync().ConfigureAwait(false);
                }
                catch (Exception) when (ct.IsCancellationRequested)
                {
                    return;
                }
            }
#endif
            using var clientDisposable = client;
            client.NoDelay = true;

            using var stream = client.GetStream();
            using var reader = new StreamReader(
                stream,
                Encoding.ASCII,
                detectEncodingFromByteOrderMarks: false,
                bufferSize: 1024,
                leaveOpen: true
            );

            string? requestLine =
#if NET8_0_OR_GREATER
            await reader.ReadLineAsync(CancellationToken.None).ConfigureAwait(false);
#else
            await reader.ReadLineAsync().ConfigureAwait(false);
#endif
            if (string.IsNullOrEmpty(requestLine))
            {
                return;
            }

            // Consume headers (no cancellation)
            string? line;
#if NET8_0_OR_GREATER
            while (
                !string.IsNullOrEmpty(line = await reader.ReadLineAsync(CancellationToken.None).ConfigureAwait(false))
            ) { }
#else
            while (!string.IsNullOrEmpty(line = await reader.ReadLineAsync().ConfigureAwait(false))) { }
#endif

            string pathAndQuery = requestLine.Split(' ')[1];

#pragma warning disable IDE0057
            var queryParams = pathAndQuery.Contains('?')
                ? pathAndQuery
                    .Substring(pathAndQuery.IndexOf('?') + 1)
                    .Split('&')
                    .Select(p => p.Split('='))
                    .Where(p => p.Length == 2)
                    .ToDictionary(p => p[0], p => WebUtility.UrlDecode(p[1]))
                : new Dictionary<string, string>();
#pragma warning restore IDE0057

            queryParams.TryGetValue("code", out var code);
            code ??= "";
            queryParams.TryGetValue("state", out var state);
            state ??= "";
            queryParams.TryGetValue("error", out var error);
            error ??= "";

            string html;
            if (!string.IsNullOrEmpty(error))
            {
                html =
                    $"<html><body>Sign-in error: {WebUtility.HtmlEncode(error)}. You may close this window.</body></html>";
            }
            else if (string.IsNullOrEmpty(code))
            {
                html = "<html><body>No authorization code found. You may close this window.</body></html>";
            }
            else
            {
                html = "<html><body>Authentication complete. You may return to Revit.</body></html>";
                // Signal the main flow before we send the response body
                tcs.TrySetResult((code, state));
            }

            byte[] body = Encoding.UTF8.GetBytes(html);

            string headers =
                "HTTP/1.1 200 OK\r\n"
                + "Content-Type: text/html; charset=utf-8\r\n"
                + "Cache-Control: no-store\r\n"
                + $"Content-Length: {body.Length}\r\n"
                + "Connection: close\r\n\r\n";

            byte[] headerBytes = Encoding.ASCII.GetBytes(headers);

            // Write without cancellation so the browser gets the full body
#if NET8_0_OR_GREATER
            await stream
                .WriteAsync(headerBytes.AsMemory(0, headerBytes.Length), CancellationToken.None)
                .ConfigureAwait(false);
            await stream.WriteAsync(body.AsMemory(0, body.Length), CancellationToken.None).ConfigureAwait(false);
            await stream.FlushAsync(CancellationToken.None).ConfigureAwait(false);
#else
            await stream.WriteAsync(headerBytes, 0, headerBytes.Length, CancellationToken.None).ConfigureAwait(false);
            await stream.WriteAsync(body, 0, body.Length, CancellationToken.None).ConfigureAwait(false);
            await stream.FlushAsync(CancellationToken.None).ConfigureAwait(false);
#endif
        }
        finally
        {
            listener.Stop();
        }
    }

    private static void OpenBrowser(string url)
    {
        try
        {
            Process.Start(new ProcessStartInfo { FileName = url, UseShellExecute = true });
        }
        catch
        {
            // Fallbacks if needed per platform
        }
    }

    // Helpers
    private static int GetFreeTcpPort()
    {
#if NET8_0_OR_GREATER
        using var listener = new TcpListener(IPAddress.Loopback, 0);
#else
        var listener = new TcpListener(IPAddress.Loopback, 0);
#endif
        listener.Start();
        int port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        return port;
    }

    private static string CreateCodeVerifier() => CreateCryptoRandomUrlSafe(64);

    private static string CreateCodeChallenge(string verifier)
    {
#if NET8_0_OR_GREATER
        byte[] hash = SHA256.HashData(Encoding.ASCII.GetBytes(verifier));
#else
        using var sha256 = SHA256.Create();
        byte[] hash = sha256.ComputeHash(Encoding.ASCII.GetBytes(verifier));
#endif
        return Base64UrlEncode(hash);
    }

    private static string CreateCryptoRandomUrlSafe(int bytes)
    {
        byte[] buffer = new byte[bytes];
#if NET8_0_OR_GREATER
        RandomNumberGenerator.Fill(buffer);
#else
        using (var rng = RandomNumberGenerator.Create())
        {
            rng.GetBytes(buffer);
        }
#endif
        return Base64UrlEncode(buffer);
    }

    private static string Base64UrlEncode(ReadOnlySpan<byte> data)
    {
#if NET8_0_OR_GREATER
        string b64 = Convert.ToBase64String(data);
#else
        string b64 = Convert.ToBase64String(data.ToArray());
#endif
        return b64.Replace("+", "-").Replace("/", "_").TrimEnd('=');
    }
}
```

</details>
