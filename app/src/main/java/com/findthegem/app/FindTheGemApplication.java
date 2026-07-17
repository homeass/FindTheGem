package com.findthegem.app;

import android.app.Application;
import android.content.Context;
import android.content.SharedPreferences;
import android.preference.PreferenceManager;

public class FindTheGemApplication extends Application {

    private static FindTheGemApplication instance;
    private SharedPreferences sharedPreferences;

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        sharedPreferences = PreferenceManager.getDefaultSharedPreferences(this);
    }

    public static FindTheGemApplication getInstance() {
        return instance;
    }

    public SharedPreferences getSharedPreferences() {
        return sharedPreferences;
    }

    public String getServerUrl() {
        return sharedPreferences.getString("server_url", "http://127.0.0.1:8501");
    }

    public void setServerUrl(String url) {
        sharedPreferences.edit().putString("server_url", url).apply();
    }
}
