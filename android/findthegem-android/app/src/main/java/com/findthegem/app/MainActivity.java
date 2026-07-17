package com.findthegem.app;

import android.annotation.SuppressLint;
import android.app.DownloadManager;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.preference.PreferenceManager;
import android.view.KeyEvent;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.DownloadListener;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private SwipeRefreshLayout swipeRefreshLayout;
    private FrameLayout loadingOverlay;
    private ProgressBar loadingProgressBar;
    private TextView loadingText;
    private FrameLayout errorOverlay;
    private TextView errorText;
    private TextView retryButton;
    private Toolbar toolbar;
    private String serverUrl;
    private boolean isLoading = false;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Full screen immersive mode
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );
        
        setContentView(R.layout.activity_main);
        
        // Initialize views
        initViews();
        
        // Get server URL from preferences
        SharedPreferences prefs = PreferenceManager.getDefaultSharedPreferences(this);
        serverUrl = prefs.getString("server_url", "http://127.0.0.1:8501");
        
        // Setup toolbar
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayShowTitleEnabled(false);
        }
        
        // Setup WebView
        setupWebView();
        
        // Setup swipe to refresh
        setupSwipeRefresh();
        
        // Load the URL
        loadUrl(serverUrl);
        
        // Handle window insets for edge-to-edge
        handleWindowInsets();
    }

    private void initViews() {
        webView = findViewById(R.id.webview);
        swipeRefreshLayout = findViewById(R.id.swipe_refresh_layout);
        loadingOverlay = findViewById(R.id.loading_overlay);
        loadingProgressBar = findViewById(R.id.loading_progress);
        loadingText = findViewById(R.id.loading_text);
        errorOverlay = findViewById(R.id.error_overlay);
        errorText = findViewById(R.id.error_text);
        retryButton = findViewById(R.id.retry_button);
        toolbar = findViewById(R.id.toolbar);
        
        loadingText.setText(R.string.loading_text);
        
        retryButton.setOnClickListener(v -> {
            errorOverlay.setVisibility(View.GONE);
            loadUrl(serverUrl);
        });
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings webSettings = webView.getSettings();
        
        // Enable JavaScript
        webSettings.setJavaScriptEnabled(true);
        
        // Enable DOM storage
        webSettings.setDomStorageEnabled(true);
        
        // Enable database storage
        webSettings.setDatabaseEnabled(true);
        
        // Enable file access
        webSettings.setAllowFileAccess(true);
        webSettings.setAllowFileAccessFromFileURLs(true);
        webSettings.setAllowUniversalAccessFromFileURLs(true);
        
        // Enable mixed content (for HTTP on HTTPS pages)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            webSettings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        }
        
        // Enable zoom
        webSettings.setBuiltInZoomControls(true);
        webSettings.setDisplayZoomControls(false);
        webSettings.setSupportZoom(true);
        
        // Enable viewport
        webSettings.setUseWideViewPort(true);
        webSettings.setLoadWithOverviewMode(true);
        
        // Enable cache
        webSettings.setCacheMode(WebSettings.LOAD_DEFAULT);
        
        // Enable geolocation
        webSettings.setGeolocationEnabled(true);
        
        // User agent
        webSettings.setUserAgentString(webSettings.getUserAgentString() + " FindTheGem/Android");
        
        // Cookie manager
        CookieManager.getInstance().setAcceptCookie(true);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true);
        }
        
        // WebViewClient for navigation handling
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                // Keep navigation within the app
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    view.loadUrl(url);
                    return true;
                }
                return false;
            }

            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                super.onPageStarted(view, url, favicon);
                isLoading = true;
                showLoading(true);
                swipeRefreshLayout.setRefreshing(true);
                toolbar.setTitle(getString(R.string.loading_title));
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                isLoading = false;
                showLoading(false);
                swipeRefreshLayout.setRefreshing(false);
                errorOverlay.setVisibility(View.GONE);
                toolbar.setTitle(view.getTitle() != null ? view.getTitle() : getString(R.string.app_name));
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                super.onReceivedError(view, request, error);
                if (request.isForMainFrame()) {
                    isLoading = false;
                    showLoading(false);
                    swipeRefreshLayout.setRefreshing(false);
                    showError(getString(R.string.error_loading_page) + ": " + error.getDescription());
                }
            }

            @Override
            public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                // For development, proceed with SSL errors (self-signed certs)
                // In production, you should handle this properly
                handler.proceed();
            }
        });
        
        // WebChromeClient for progress and title
        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                super.onProgressChanged(view, newProgress);
                loadingProgressBar.setProgress(newProgress);
                if (newProgress < 100) {
                    loadingText.setText(getString(R.string.loading_progress, newProgress));
                } else {
                    loadingText.setText(R.string.loading_complete);
                }
            }

            @Override
            public void onReceivedTitle(WebView view, String title) {
                super.onReceivedTitle(view, title);
                if (getSupportActionBar() != null && !isLoading) {
                    getSupportActionBar().setTitle(title != null ? title : getString(R.string.app_name));
                }
            }
        });

        webView.setDownloadListener((url, userAgent, contentDisposition, mimeType, contentLength) -> {
            try {
                DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                String fileName = contentDisposition;
                if (fileName != null && fileName.contains("filename=")) {
                    fileName = fileName.substring(fileName.indexOf("filename=") + 9);
                    fileName = fileName.replaceAll("[\"']", "").trim();
                } else {
                    fileName = "download_" + System.currentTimeMillis();
                }
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOCUMENTS, "FindTheGem/" + fileName);
                request.setTitle(fileName);
                request.setMimeType(mimeType);
                request.addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url));

                DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
                dm.enqueue(request);
                Toast.makeText(this, "Downloading: " + fileName, Toast.LENGTH_SHORT).show();
            } catch (Exception e) {
                Toast.makeText(this, "Download failed: " + e.getMessage(), Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void setupSwipeRefresh() {
        swipeRefreshLayout.setColorSchemeResources(
            R.color.colorPrimary,
            R.color.colorSecondary,
            R.color.colorAccent
        );
        swipeRefreshLayout.setOnRefreshListener(() -> {
            if (webView != null) {
                webView.reload();
            }
        });
    }

    private void handleWindowInsets() {
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main_container), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });
    }

    private void loadUrl(String url) {
        if (webView != null && url != null && !url.isEmpty()) {
            // Ensure URL has protocol
            if (!url.startsWith("http://") && !url.startsWith("https://")) {
                url = "http://" + url;
            }
            webView.loadUrl(url);
        }
    }

    private void showLoading(boolean show) {
        if (show) {
            loadingOverlay.setVisibility(View.VISIBLE);
            loadingProgressBar.setProgress(0);
            loadingText.setText(R.string.loading_text);
        } else {
            loadingOverlay.setVisibility(View.GONE);
        }
    }

    private void showError(String message) {
        errorText.setText(message);
        errorOverlay.setVisibility(View.VISIBLE);
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.main_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        int id = item.getItemId();
        
        if (id == R.id.action_settings) {
            startActivity(new Intent(this, SettingsActivity.class));
            return true;
        } else if (id == R.id.action_refresh) {
            if (webView != null) {
                webView.reload();
            }
            return true;
        } else if (id == R.id.action_home) {
            loadUrl(serverUrl);
            return true;
        } else if (id == R.id.action_back) {
            if (webView != null && webView.canGoBack()) {
                webView.goBack();
            }
            return true;
        } else if (id == R.id.action_forward) {
            if (webView != null && webView.canGoForward()) {
                webView.goForward();
            }
            return true;
        }
        
        return super.onOptionsItemSelected(item);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        // Handle back button
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (webView != null && webView.canGoBack()) {
                webView.goBack();
                return true;
            } else {
                // Show exit confirmation dialog
                showExitDialog();
                return true;
            }
        }
        return super.onKeyDown(keyCode, event);
    }

    private void showExitDialog() {
        new AlertDialog.Builder(this)
            .setTitle(R.string.exit_confirm_title)
            .setMessage(R.string.exit_confirm_message)
            .setPositiveButton(R.string.exit_yes, (dialog, which) -> finish())
            .setNegativeButton(R.string.exit_no, null)
            .show();
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
        hideSystemBars();
    }

    @Override
    protected void onPause() {
        super.onPause();
        webView.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
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
}
