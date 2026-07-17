package com.findthegem.app;

import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.preference.PreferenceManager;
import android.view.MenuItem;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;

import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.textfield.TextInputLayout;

public class SettingsActivity extends AppCompatActivity {

    private TextInputEditText serverUrlInput;
    private TextInputLayout urlInputLayout;
    private Button testConnectionButton;
    private Button saveButton;
    private Button resetButton;
    private TextView currentUrlText;
    private SharedPreferences sharedPreferences;
    private static final String DEFAULT_URL = "http://127.0.0.1:8501";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_settings);

        // Initialize views
        initViews();

        // Setup toolbar
        Toolbar toolbar = findViewById(R.id.settings_toolbar);
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
            getSupportActionBar().setDisplayShowHomeEnabled(true);
            getSupportActionBar().setTitle(R.string.settings_title);
        }

        // Get shared preferences
        sharedPreferences = PreferenceManager.getDefaultSharedPreferences(this);

        // Load current URL
        loadCurrentUrl();

        // Setup click listeners
        setupClickListeners();
    }

    private void initViews() {
        serverUrlInput = findViewById(R.id.server_url_input);
        urlInputLayout = findViewById(R.id.url_input_layout);
        testConnectionButton = findViewById(R.id.test_connection_button);
        saveButton = findViewById(R.id.save_button);
        resetButton = findViewById(R.id.reset_button);
        currentUrlText = findViewById(R.id.current_url_text);
    }

    private void loadCurrentUrl() {
        String currentUrl = sharedPreferences.getString("server_url", DEFAULT_URL);
        serverUrlInput.setText(currentUrl);
        currentUrlText.setText(getString(R.string.current_url_label) + " " + currentUrl);
        currentUrlText.setVisibility(View.VISIBLE);
    }

    private void setupClickListeners() {
        // Test connection button
        testConnectionButton.setOnClickListener(v -> testConnection());

        // Save button
        saveButton.setOnClickListener(v -> saveUrl());

        // Reset button
        resetButton.setOnClickListener(v -> resetToDefault());
    }

    private void testConnection() {
        String url = serverUrlInput.getText().toString().trim();
        
        if (url.isEmpty()) {
            urlInputLayout.setError(getString(R.string.url_required_error));
            return;
        }

        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            urlInputLayout.setError(getString(R.string.invalid_url_error));
            return;
        }

        urlInputLayout.setError(null);
        testConnectionButton.setEnabled(false);
        testConnectionButton.setText(R.string.testing_connection);

        // Create a temporary WebView to test the connection
        WebView testWebView = new WebView(this);
        testWebView.getSettings().setJavaScriptEnabled(true);
        testWebView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                runOnUiThread(() -> {
                    testConnectionButton.setEnabled(true);
                    testConnectionButton.setText(R.string.test_connection);
                    Toast.makeText(SettingsActivity.this, R.string.connection_success, Toast.LENGTH_SHORT).show();
                    view.destroy();
                });
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String description, String failingUrl) {
                runOnUiThread(() -> {
                    testConnectionButton.setEnabled(true);
                    testConnectionButton.setText(R.string.test_connection);
                    Toast.makeText(SettingsActivity.this, 
                        getString(R.string.connection_failed) + ": " + description, Toast.LENGTH_LONG).show();
                    view.destroy();
                });
            }
        });

        testWebView.loadUrl(url);
    }

    private void saveUrl() {
        String url = serverUrlInput.getText().toString().trim();
        
        if (url.isEmpty()) {
            urlInputLayout.setError(getString(R.string.url_required_error));
            return;
        }

        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            urlInputLayout.setError(getString(R.string.invalid_url_error));
            return;
        }

        urlInputLayout.setError(null);
        
        sharedPreferences.edit().putString("server_url", url).apply();
        
        Toast.makeText(this, R.string.url_saved_success, Toast.LENGTH_SHORT).show();
        
        // Update current URL display
        currentUrlText.setText(getString(R.string.current_url_label) + " " + url);
        
        // Return to main activity with result
        Intent resultIntent = new Intent();
        resultIntent.putExtra("server_url", url);
        setResult(RESULT_OK, resultIntent);
        finish();
    }

    private void resetToDefault() {
        serverUrlInput.setText(DEFAULT_URL);
        sharedPreferences.edit().putString("server_url", DEFAULT_URL).apply();
        currentUrlText.setText(getString(R.string.current_url_label) + " " + DEFAULT_URL);
        Toast.makeText(this, R.string.url_reset_success, Toast.LENGTH_SHORT).show();
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        if (item.getItemId() == android.R.id.home) {
            finish();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }
}
