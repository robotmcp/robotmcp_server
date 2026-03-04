"""HTML templates for OAuth and CLI login flows.

These templates are shared across main.py and setup.py
to eliminate duplication.

Claude theme colors:
- Background: #FAF9F7 (warm cream)
- Primary: #D97756 (terracotta)
- Primary hover: #C4684A
- Text: #1A1915 (dark charcoal)
- Secondary text: #6B6860
- Border: #E5E4E0, #D9D8D4
"""

# ============== OAuth Flow Templates ==============

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - RobotMCP</title>
    <style>
        body {{ font-family: 'Söhne', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #FAF9F7;
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                     width: 100%; max-width: 400px; border: 1px solid #E5E4E0; }}
        h1 {{ margin: 0 0 8px; color: #1A1915; font-size: 24px; font-weight: 600; }}
        p {{ color: #6B6860; margin: 0 0 24px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #1A1915; font-weight: 500; font-size: 14px; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px 14px; border: 1px solid #D9D8D4; border-radius: 8px;
            font-size: 15px; box-sizing: border-box; transition: all 0.2s; background: #FAF9F7; }}
        input:focus {{ outline: none; border-color: #D97756; box-shadow: 0 0 0 3px rgba(217,119,86,0.1); }}
        button {{ width: 100%; padding: 14px; background: #D97756;
                 color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
                 cursor: pointer; transition: all 0.2s; }}
        button:hover {{ background: #C4684A; }}
        .error {{ background: #FEF2F2; color: #B91C1C; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #FECACA; }}
        .success {{ background: #D1FAE5; color: #065F46; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #A7F3D0; }}
        .info {{ background: #F5F5F0; color: #6B6860; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .signup-link {{ text-align: center; margin-top: 20px; color: #6B6860; }}
        .signup-link a {{ color: #D97756; text-decoration: none; font-weight: 500; }}
        .signup-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Sign In</h1>
        <p>Sign in to authorize MCP client access</p>
        {error}
        {success}
        <div class="info">MCP client is requesting access to server tools.</div>
        <form method="POST" action="/login">
            <input type="hidden" name="session" value="{session}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Your password">
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="signup-link">
            Don't have an account? <a href="/signup?session={session}">Sign up</a>
        </div>
    </div>
</body>
</html>
"""

SIGNUP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sign Up - RobotMCP</title>
    <style>
        body {{ font-family: 'Söhne', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #FAF9F7;
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                     width: 100%; max-width: 400px; border: 1px solid #E5E4E0; }}
        h1 {{ margin: 0 0 8px; color: #1A1915; font-size: 24px; font-weight: 600; }}
        p {{ color: #6B6860; margin: 0 0 24px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #1A1915; font-weight: 500; font-size: 14px; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px 14px; border: 1px solid #D9D8D4; border-radius: 8px;
            font-size: 15px; box-sizing: border-box; transition: all 0.2s; background: #FAF9F7; }}
        input:focus {{ outline: none; border-color: #D97756; box-shadow: 0 0 0 3px rgba(217,119,86,0.1); }}
        button {{ width: 100%; padding: 14px; background: #D97756;
                 color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
                 cursor: pointer; transition: all 0.2s; }}
        button:hover {{ background: #C4684A; }}
        .error {{ background: #FEF2F2; color: #B91C1C; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #FECACA; }}
        .info {{ background: #F5F5F0; color: #6B6860; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .login-link {{ text-align: center; margin-top: 20px; color: #6B6860; }}
        .login-link a {{ color: #D97756; text-decoration: none; font-weight: 500; }}
        .login-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Create Account</h1>
        <p>Sign up to use RobotMCP</p>
        {error}
        <div class="info">Create an account to authorize MCP client access.</div>
        <form method="POST" action="/signup">
            <input type="hidden" name="session" value="{session}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Create a password" minlength="6">
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" required placeholder="Confirm your password" minlength="6">
            </div>
            <button type="submit">Create Account</button>
        </form>
        <div class="login-link">
            Already have an account? <a href="/login?session={session}">Sign in</a>
        </div>
    </div>
</body>
</html>
"""

CONSENT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authorize - RobotMCP</title>
    <style>
        body {{ font-family: 'Söhne', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #FAF9F7;
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                     width: 100%; max-width: 450px; border: 1px solid #E5E4E0; }}
        h1 {{ margin: 0 0 8px; color: #1A1915; font-size: 24px; font-weight: 600; }}
        .app-info {{ display: flex; align-items: center; gap: 15px; padding: 20px; background: #F5F5F0;
                    border-radius: 8px; margin: 20px 0; }}
        .app-icon {{ width: 50px; height: 50px; background: #D97756; border-radius: 10px;
                    display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; font-weight: 600; }}
        .app-name {{ font-weight: 600; color: #1A1915; }}
        .scopes {{ margin: 20px 0; }}
        .scope {{ display: flex; align-items: center; gap: 10px; padding: 12px; background: #F5F5F0;
                 border-radius: 8px; margin-bottom: 10px; }}
        .scope-icon {{ color: #D97756; font-weight: bold; }}
        .user-info {{ color: #6B6860; font-size: 14px; margin-bottom: 20px; }}
        .buttons {{ display: flex; gap: 12px; }}
        button {{ flex: 1; padding: 14px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s; }}
        .allow {{ background: #D97756; color: white; border: none; }}
        .deny {{ background: white; color: #6B6860; border: 1px solid #D9D8D4; }}
        .allow:hover {{ background: #C4684A; }}
        .deny:hover {{ background: #F5F5F0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Authorize Access</h1>
        <div class="user-info">Logged in as: {user_email}</div>
        <div class="app-info">
            <div class="app-icon">M</div>
            <div>
                <div class="app-name">MCP Client</div>
                <div style="color: #6B6860; font-size: 14px;">wants to access your account</div>
            </div>
        </div>
        <div class="scopes">
            <div class="scope">
                <span class="scope-icon">✓</span>
                <span>Access server tools</span>
            </div>
            <div class="scope">
                <span class="scope-icon">✓</span>
                <span>Read basic profile information</span>
            </div>
        </div>
        <form method="POST" action="/consent">
            <input type="hidden" name="session" value="{session}">
            <div class="buttons">
                <button type="submit" name="action" value="deny" class="deny">Deny</button>
                <button type="submit" name="action" value="allow" class="allow">Allow</button>
            </div>
        </form>
    </div>
</body>
</html>
"""


# ============== CLI Login Templates ==============

CLI_LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>CLI Login - RobotMCP</title>
    <style>
        body {{ font-family: 'Söhne', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #FAF9F7;
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                     width: 100%; max-width: 400px; border: 1px solid #E5E4E0; }}
        h1 {{ margin: 0 0 8px; color: #1A1915; font-size: 24px; font-weight: 600; }}
        p {{ color: #6B6860; margin: 0 0 24px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #1A1915; font-weight: 500; font-size: 14px; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px 14px; border: 1px solid #D9D8D4; border-radius: 8px;
            font-size: 15px; box-sizing: border-box; transition: all 0.2s; background: #FAF9F7; }}
        input:focus {{ outline: none; border-color: #D97756; box-shadow: 0 0 0 3px rgba(217,119,86,0.1); }}
        button {{ width: 100%; padding: 14px; background: #D97756;
                 color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
                 cursor: pointer; transition: all 0.2s; }}
        button:hover {{ background: #C4684A; }}
        .error {{ background: #FEF2F2; color: #B91C1C; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #FECACA; }}
        .info {{ background: #F5F5F0; color: #6B6860; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .signup-link {{ text-align: center; margin-top: 20px; color: #6B6860; }}
        .signup-link a {{ color: #D97756; text-decoration: none; font-weight: 500; }}
        .signup-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>CLI Login</h1>
        <p>Sign in to configure your MCP server</p>
        {error}
        <div class="info">This will authenticate your local MCP server installation.</div>
        <form method="POST" action="/cli-login">
            <input type="hidden" name="session" value="{session}">
            <input type="hidden" name="port" value="{port}">
            <input type="hidden" name="host" value="{host}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Your password">
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="signup-link">
            Don't have an account? <a href="/cli-signup?session={session}&port={port}&host={host}">Sign up</a>
        </div>
    </div>
</body>
</html>
"""

CLI_SIGNUP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>CLI Sign Up - RobotMCP</title>
    <style>
        body {{ font-family: 'Söhne', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #FAF9F7;
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
                     width: 100%; max-width: 400px; border: 1px solid #E5E4E0; }}
        h1 {{ margin: 0 0 8px; color: #1A1915; font-size: 24px; font-weight: 600; }}
        p {{ color: #6B6860; margin: 0 0 24px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #1A1915; font-weight: 500; font-size: 14px; }}
        .optional {{ color: #9B9990; font-weight: 400; font-size: 13px; }}
        input[type="email"], input[type="password"], input[type="text"] {{
            width: 100%; padding: 12px 14px; border: 1px solid #D9D8D4; border-radius: 8px;
            font-size: 15px; box-sizing: border-box; transition: all 0.2s; background: #FAF9F7; }}
        input:focus {{ outline: none; border-color: #D97756; box-shadow: 0 0 0 3px rgba(217,119,86,0.1); }}
        button {{ width: 100%; padding: 14px; background: #D97756;
                 color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
                 cursor: pointer; transition: all 0.2s; }}
        button:hover {{ background: #C4684A; }}
        .error {{ background: #FEF2F2; color: #B91C1C; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #FECACA; }}
        .info {{ background: #F5F5F0; color: #6B6860; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .login-link {{ text-align: center; margin-top: 20px; color: #6B6860; }}
        .login-link a {{ color: #D97756; text-decoration: none; font-weight: 500; }}
        .login-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Create Account</h1>
        <p>Sign up to use RobotMCP</p>
        {error}
        <div class="info">Create an account to configure your MCP server.</div>
        <form method="POST" action="/cli-signup">
            <input type="hidden" name="session" value="{session}">
            <input type="hidden" name="port" value="{port}">
            <input type="hidden" name="host" value="{host}">
            <div class="form-group">
                <label for="name">Name</label>
                <input type="text" id="name" name="name" required placeholder="Your name">
            </div>
            <div class="form-group">
                <label for="organization">Organization <span class="optional">(optional)</span></label>
                <input type="text" id="organization" name="organization" placeholder="Your organization">
            </div>
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Create a password" minlength="6">
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" required placeholder="Confirm your password" minlength="6">
            </div>
            <button type="submit">Create Account</button>
        </form>
        <div class="login-link">
            Already have an account? <a href="/cli-login?session={session}&port={port}&host={host}">Sign in</a>
        </div>
    </div>
</body>
</html>
"""
