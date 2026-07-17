package com.findthegem.app;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;

public class TermuxManager {

    private static final String TAG = "TermuxManager";
    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String SERVER_URL = "http://127.0.0.1:8501";
    private static final String ASSETS_DIR = "findthegem";
    private static final String DOCUMENTS_SUBDIR = "FindTheGem";
    private static final long POLL_INTERVAL_MS = 2000;
    private static final long FIRST_RUN_POLL_MS = 90000;
    private static final long FULL_POLL_MS = 120000;

    public interface TermuxCallback {
        void onStatusChanged(String status);
        void onReady();
        void onError(String error);
        void onNeedManualSetup(String command);
    }

    public boolean isTermuxInstalled(Context context) {
        try {
            context.getPackageManager().getPackageInfo(TERMUX_PACKAGE, 0);
            return true;
        } catch (PackageManager.NameNotFoundException e) {
            return false;
        }
    }

    private File getDocumentsDir() {
        File docs = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS);
        return new File(docs, DOCUMENTS_SUBDIR);
    }

    public void setupAndStartServer(Context context, TermuxCallback callback) {
        new Thread(() -> {
            try {
                callback.onStatusChanged(context.getString(R.string.setup_copying_files));
                boolean copied = copyAssetsToStorage(context);
                if (!copied) {
                    callback.onError(context.getString(R.string.setup_error_files_failed));
                    return;
                }

                String sdcardPath = getDocumentsDir().getAbsolutePath();
                String combined = "bash " + sdcardPath + "/setup.sh && bash " + sdcardPath + "/start_server.sh";

                callback.onStatusChanged(context.getString(R.string.setup_starting_server));
                boolean sent = runTermuxCommand(context, combined);
                if (!sent) {
                    callback.onError(context.getString(R.string.setup_error_server_failed));
                    return;
                }

                callback.onStatusChanged(context.getString(R.string.setup_waiting_server));

                boolean ready = pollServerReady(FIRST_RUN_POLL_MS);
                if (ready) {
                    callback.onReady();
                    return;
                }

                Log.d(TAG, "Quick poll failed, trying bootstrap fallback");
                String bootstrapCmd = "bash " + sdcardPath + "/bootstrap.sh";
                callback.onNeedManualSetup(bootstrapCmd);

            } catch (Exception e) {
                Log.e(TAG, "Setup failed", e);
                callback.onError(context.getString(R.string.setup_error_server_failed));
            }
        }).start();
    }

    public void retryAfterBootstrap(Context context, TermuxCallback callback) {
        new Thread(() -> {
            try {
                String sdcardPath = getDocumentsDir().getAbsolutePath();
                String combined = "bash " + sdcardPath + "/setup.sh && bash " + sdcardPath + "/start_server.sh";

                callback.onStatusChanged(context.getString(R.string.setup_starting_server));
                boolean sent = runTermuxCommand(context, combined);
                if (!sent) {
                    callback.onError(context.getString(R.string.setup_error_server_failed));
                    return;
                }

                callback.onStatusChanged(context.getString(R.string.setup_waiting_server));
                boolean ready = pollServerReady(FULL_POLL_MS);

                if (ready) {
                    callback.onReady();
                } else {
                    callback.onError(context.getString(R.string.setup_error_server_failed));
                }
            } catch (Exception e) {
                Log.e(TAG, "Retry failed", e);
                callback.onError(context.getString(R.string.setup_error_server_failed));
            }
        }).start();
    }

    public void stopServer(Context context) {
        new Thread(() -> {
            try {
                String sdcardPath = getDocumentsDir().getAbsolutePath();
                runTermuxCommand(context, "bash " + sdcardPath + "/stop_server.sh");
            } catch (Exception e) {
                Log.e(TAG, "Failed to stop server", e);
            }
        }).start();
    }

    private boolean copyAssetsToStorage(Context context) {
        File destDir = getDocumentsDir();
        if (!destDir.exists() && !destDir.mkdirs()) {
            Log.e(TAG, "Failed to create directory: " + destDir);
            return false;
        }

        try {
            String[] files = context.getAssets().list(ASSETS_DIR);
            if (files == null || files.length == 0) {
                Log.e(TAG, "No files found in assets/" + ASSETS_DIR);
                return false;
            }

            for (String filename : files) {
                copyAssetFile(context, ASSETS_DIR + "/" + filename,
                        new File(destDir, filename));
            }
            return true;
        } catch (IOException e) {
            Log.e(TAG, "Failed to copy assets", e);
            return false;
        }
    }

    private void copyAssetFile(Context context, String assetPath, File destFile) throws IOException {
        String[] subFiles = context.getAssets().list(assetPath);
        if (subFiles != null && subFiles.length > 0) {
            if (!destFile.exists()) {
                destFile.mkdirs();
            }
            for (String sub : subFiles) {
                copyAssetFile(context, assetPath + "/" + sub, new File(destFile, sub));
            }
            return;
        }

        try (InputStream in = context.getAssets().open(assetPath);
             OutputStream out = new FileOutputStream(destFile)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
        }
        Log.d(TAG, "Copied asset: " + assetPath + " → " + destFile.getAbsolutePath());
    }

    private static final String TERMUX_BASH = "/data/data/com.termux/files/usr/bin/bash";

    private boolean runTermuxCommand(Context context, String command) {
        try {
            Intent intent = new Intent("com.termux.RUN_COMMAND");
            intent.setClassName(TERMUX_PACKAGE, "com.termux.app.RunCommandService");
            intent.putExtra("com.termux.RUN_COMMAND_PATH", TERMUX_BASH);
            intent.putExtra("com.termux.RUN_COMMAND_ARGUMENTS", new String[]{"-c", command});
            intent.putExtra("com.termux.RUN_COMMAND_BACKGROUND", true);

            context.startService(intent);
            Log.d(TAG, "Sent Termux RUN_COMMAND: bash -c \"" + command + "\"");
            return true;
        } catch (Exception e) {
            Log.e(TAG, "Failed to send Termux command: " + command, e);
            return false;
        }
    }

    private boolean pollServerReady(long maxWaitMs) {
        long startTime = System.currentTimeMillis();

        while (System.currentTimeMillis() - startTime < maxWaitMs) {
            try {
                URL url = new URL(SERVER_URL);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(3000);
                conn.setReadTimeout(3000);
                int responseCode = conn.getResponseCode();
                conn.disconnect();

                if (responseCode == 200) {
                    Log.d(TAG, "Server is ready (HTTP 200)");
                    return true;
                }
            } catch (IOException e) {
                Log.d(TAG, "Server not ready, retrying... (" + e.getMessage() + ")");
            } catch (Exception e) {
                Log.d(TAG, "Unexpected error polling server", e);
            }

            try {
                Thread.sleep(POLL_INTERVAL_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }

        Log.e(TAG, "Server did not become ready within " + maxWaitMs + "ms");
        return false;
    }

    public static void copyCommandToClipboard(Context context, String command) {
        ClipboardManager clipboard = (ClipboardManager) context.getSystemService(Context.CLIPBOARD_SERVICE);
        ClipData clip = ClipData.newPlainText("FindTheGem setup", command);
        clipboard.setPrimaryClip(clip);
        Log.d(TAG, "Copied to clipboard: " + command);
    }

    public static void openTermux(Context context) {
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(TERMUX_PACKAGE);
        if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(intent);
        }
    }
}
