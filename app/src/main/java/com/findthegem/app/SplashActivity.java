package com.findthegem.app;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import android.util.Log;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;

public class SplashActivity extends AppCompatActivity {

    private ProgressBar setupProgress;
    private TextView setupStatusText;
    private LinearLayout setupErrorContainer;
    private TextView setupErrorText;
    private Button setupRetryButton;
    private Button setupTermuxButton;

    private TermuxManager termuxManager;
    private boolean waitingForBootstrap = false;

    private final ActivityResultLauncher<Intent> safLauncher =
        registerForActivityResult(
            new ActivityResultContracts.StartActivityForResult(),
            result -> {
                if (isStoragePermissionGranted()) {
                    startServerSetup();
                } else {
                    showError("Storage permission is required to run the local server.", false);
                }
            }
        );

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );

        setContentView(R.layout.activity_splash);
        hideSystemBars();

        TextView appNameText = findViewById(R.id.app_name_text);
        appNameText.setText(getString(R.string.app_name));

        setupProgress = findViewById(R.id.setup_progress);
        setupStatusText = findViewById(R.id.setup_status_text);
        setupErrorContainer = findViewById(R.id.setup_error_container);
        setupErrorText = findViewById(R.id.setup_error_text);
        setupRetryButton = findViewById(R.id.setup_retry_button);
        setupTermuxButton = findViewById(R.id.setup_termux_button);

        setupRetryButton.setOnClickListener(v -> {
            if (waitingForBootstrap) {
                waitingForBootstrap = false;
                startRetryAfterBootstrap();
            } else {
                checkAndStartSetup();
            }
        });
        setupTermuxButton.setOnClickListener(v -> {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW,
                    Uri.parse("https://f-droid.org/en/packages/com.termux/")));
            } catch (Exception ignored) {}
        });

        termuxManager = new TermuxManager();
        checkAndStartSetup();
    }

    private void checkAndStartSetup() {
        Log.d("SplashActivity", "checkAndStartSetup called");
        setupErrorContainer.setVisibility(View.GONE);
        setupRetryButton.setVisibility(View.GONE);
        setupTermuxButton.setVisibility(View.GONE);

        boolean termuxInstalled = termuxManager.isTermuxInstalled(this);
        Log.d("SplashActivity", "Termux installed: " + termuxInstalled);
        if (!termuxInstalled) {
            showError(getString(R.string.setup_error_termux_not_found), true);
            return;
        }

        boolean storageGranted = isStoragePermissionGranted();
        Log.d("SplashActivity", "Storage permission granted: " + storageGranted
            + " (SDK=" + Build.VERSION.SDK_INT + ")");
        if (!storageGranted) {
            requestStoragePermission();
            return;
        }

        // Check Termux RUN_COMMAND permission (dangerous permission)
        if (checkSelfPermission("com.termux.permission.RUN_COMMAND")
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            Log.d("SplashActivity", "Requesting RUN_COMMAND permission");
            requestPermissions(new String[]{"com.termux.permission.RUN_COMMAND"}, 200);
            return;
        }

        Log.d("SplashActivity", "All checks passed, starting server setup");
        startServerSetup();
    }

    private boolean isStoragePermissionGranted() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            boolean result = Environment.isExternalStorageManager();
            Log.d("SplashActivity", "isExternalStorageManager=" + result);
            return result;
        } else {
            return checkSelfPermission(android.Manifest.permission.WRITE_EXTERNAL_STORAGE)
                    == android.content.pm.PackageManager.PERMISSION_GRANTED;
        }
    }

    private void requestStoragePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Intent intent = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION);
            intent.setData(Uri.parse("package:" + getPackageName()));
            try {
                safLauncher.launch(intent);
            } catch (Exception e) {
                Intent fallback = new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION);
                safLauncher.launch(fallback);
            }
        } else {
            requestPermissions(
                new String[]{android.Manifest.permission.WRITE_EXTERNAL_STORAGE},
                100
            );
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == 100 || requestCode == 200) {
            if (grantResults.length > 0
                    && grantResults[0] == android.content.pm.PackageManager.PERMISSION_GRANTED) {
                checkAndStartSetup();
            } else {
                if (requestCode == 100) {
                    showError("Storage permission is required.", false);
                } else {
                    showError("Termux RUN_COMMAND permission is required.\n\nPlease grant it in Settings → Apps → Find the Gem → Permissions.", false);
                }
            }
        }
    }

    private void startServerSetup() {
        setupProgress.setVisibility(View.VISIBLE);
        setupStatusText.setVisibility(View.VISIBLE);
        updateStatus(getString(R.string.setup_copying_files));

        termuxManager.setupAndStartServer(this, new TermuxManager.TermuxCallback() {
            @Override
            public void onStatusChanged(String status) {
                runOnUiThread(() -> updateStatus(status));
            }

            @Override
            public void onReady() {
                runOnUiThread(() -> {
                    updateStatus(getString(R.string.setup_complete));
                    setupProgress.setVisibility(View.GONE);
                    navigateToMain();
                });
            }

            @Override
            public void onError(String error) {
                runOnUiThread(() -> showError(error, false));
            }

            @Override
            public void onNeedManualSetup(String command) {
                runOnUiThread(() -> {
                    waitingForBootstrap = true;
                    setupProgress.setVisibility(View.GONE);
                    setupStatusText.setVisibility(View.GONE);
                    TermuxManager.copyCommandToClipboard(SplashActivity.this, command);
                    TermuxManager.openTermux(SplashActivity.this);
                    String msg = getString(R.string.setup_bootstrap_instruction) + "\n\n"
                            + command;
                    setupErrorContainer.setVisibility(View.VISIBLE);
                    setupErrorText.setText(msg);
                    setupRetryButton.setVisibility(View.VISIBLE);
                    setupTermuxButton.setVisibility(View.GONE);
                });
            }
        });
    }

    private void startRetryAfterBootstrap() {
        setupErrorContainer.setVisibility(View.GONE);
        setupProgress.setVisibility(View.VISIBLE);
        setupStatusText.setVisibility(View.VISIBLE);

        termuxManager.retryAfterBootstrap(this, new TermuxManager.TermuxCallback() {
            @Override
            public void onStatusChanged(String status) {
                runOnUiThread(() -> updateStatus(status));
            }

            @Override
            public void onReady() {
                runOnUiThread(() -> {
                    updateStatus(getString(R.string.setup_complete));
                    setupProgress.setVisibility(View.GONE);
                    navigateToMain();
                });
            }

            @Override
            public void onError(String error) {
                runOnUiThread(() -> showError(error, false));
            }

            @Override
            public void onNeedManualSetup(String command) {
                runOnUiThread(() -> showError("Setup still incomplete. Please try again.", false));
            }
        });
    }

    private void updateStatus(String status) {
        setupStatusText.setText(status);
    }

    private void showError(String message, boolean showTermuxButton) {
        setupProgress.setVisibility(View.GONE);
        setupStatusText.setVisibility(View.GONE);
        setupErrorContainer.setVisibility(View.VISIBLE);
        setupErrorText.setText(message);
        setupRetryButton.setVisibility(View.VISIBLE);
        setupTermuxButton.setVisibility(showTermuxButton ? View.VISIBLE : View.GONE);
    }

    private void navigateToMain() {
        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            Intent intent = new Intent(SplashActivity.this, MainActivity.class);
            startActivity(intent);
            finish();
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }, 800);
    }

    private void hideSystemBars() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController insetsController = getWindow().getInsetsController();
            if (insetsController != null) {
                insetsController.hide(WindowInsets.Type.systemBars());
                insetsController.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
            }
        } else {
            getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
            );
        }
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideSystemBars();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
    }
}
