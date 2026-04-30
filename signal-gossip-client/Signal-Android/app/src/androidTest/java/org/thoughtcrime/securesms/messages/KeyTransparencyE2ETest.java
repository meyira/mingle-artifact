package org.thoughtcrime.securesms.messages;
import androidx.recyclerview.widget.RecyclerView;
import androidx.test.espresso.UiController;
import androidx.test.espresso.ViewAction;
import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.espresso.contrib.RecyclerViewActions;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.hamcrest.Matcher;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.thoughtcrime.securesms.MainActivity;
import org.thoughtcrime.securesms.R;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.closeSoftKeyboard;
import static androidx.test.espresso.action.ViewActions.longClick;
import static androidx.test.espresso.action.ViewActions.replaceText;
import static androidx.test.espresso.action.ViewActions.typeText;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.RootMatchers.isPlatformPopup;
import static androidx.test.espresso.matcher.ViewMatchers.hasDescendant;
import static androidx.test.espresso.matcher.ViewMatchers.isAssignableFrom;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withContentDescription;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;

import static org.hamcrest.Matchers.allOf;

import android.view.View;
import android.widget.EditText;

@RunWith(AndroidJUnit4.class)
public class KeyTransparencyE2ETest {
    @Rule
    public ActivityScenarioRule<MainActivity> activityRule =
            new ActivityScenarioRule<>(MainActivity.class);


    @Test
    public void testSendGossipMessageAndMeasurePayload() throws InterruptedException {
        String[] testStrings = {
                ".",
                "Ack.",
                "Are we meeting at the main campus today?",
                "He founded Signal: https://en.wikipedia.org/wiki/Moxie_Marlinspike",
                "Testing the throughput \uD83D\uDE84",
                "Please check the **Security logs!**",
                "End to End Encryption is nice, but there is one question: How do we exchange our public keys? If we rely on somebody else, we are risking that they will do a MITM attack on us. How about Key Transparency?",
                "2026-02-06 09:47:40.759 23079-23109 AlarmSleepTimer         org.thoughtcrime.securesms           W  Setting an inexact alarm to wake up in 20000ms. CanScheduleAlarms: false 2026-02-06 09:47:40.832 23079-23109 LibSignalChatConnection org.thoughtcrime.securesms           D  [libsignal-auth:200761730] [sendKeepAlive] Success 2026-02-06 09:47:40.888 23079-23109 LibSignalChatConnection org.thoughtcrime.securesms           D  [libsignal-unauth:63660783] [sendKeepAlive] Success 2026-02-06 09:47:41.675 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=499.78ms min=499.49ms max=500.01ms count=3 2026-02-06 09:47:42.675 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=500.05ms min=499.93ms max=500.17ms count=2 2026-02-06 09:47:43.676 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=500.21ms min=500.20ms max=500.22ms count=2 2026-02-06 09:47:45.175 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=499.88ms min=499.79ms max=500.01ms count=3 2026-02-06 09:47:46.176 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=500.12ms min=499.88ms max=500.36ms count=2 2026-02-06 09:47:47.176 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=500.01ms min=499.81ms max=500.22ms count=2 2026-02-06 09:47:48.176 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=500.07ms min=499.69ms max=500.45ms count=2 2026-02-06 09:47:49.676 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=500.01ms min=499.78ms max=500.16ms count=3 2026-02-06 09:47:51.175 23079-23129 EGL_emulation           org.thoughtcrime.securesms           D  app_time_stats: avg=499.78ms min=499.46ms max=500.12ms count=3",
        };


        String contactName = "Test User"; // FIXME REDACT REDACT REDACT IN THE FINAL HAND-IN!!!!

        onView(withId(R.id.list)).check(matches(isDisplayed()));

        onView(withId(R.id.list))
                .perform(RecyclerViewActions.actionOnItem(
                        hasDescendant(withText(contactName)),
                        click()
                ));

        for (int i = 0; i < testStrings.length; i++) {
            String message = testStrings[i];
            onView(withId(R.id.embedded_text_editor))
                    .perform(replaceText(message), closeSoftKeyboard());
            if (i == 3) {
                // Wait until the Link preview has been generated
                Thread.sleep(1000);
            }
            if (i == 5) {
                int start = testStrings[i].indexOf("Security logs!");
                int end = start + "Security logs!".length();
                onView(withId(R.id.embedded_text_editor)).perform(selectTextRange(start, end));
                onView(withId(R.id.embedded_text_editor)).perform(longClick());
                onView(withText(org.hamcrest.Matchers.containsStringIgnoringCase("Bold")))
                        .inRoot(isPlatformPopup())
                        .perform(click());
            }
            else if (i == 7) {
                int start = 0;
                int end = start + testStrings[i].length();
                onView(withId(R.id.embedded_text_editor)).perform(selectTextRange(start, end));
                onView(withId(R.id.embedded_text_editor)).perform(longClick());
                onView(withContentDescription("More options"))
                        .inRoot(isPlatformPopup())
                        .perform(click());

                onView(withText("Monospace"))
                        .inRoot(isPlatformPopup())
                        .perform(click());
            }

            onView(withId(R.id.send_button))
                    .perform(click());
        }

    }

    public static ViewAction selectTextRange(final int start, final int end) {
        return new ViewAction() {
            @Override
            public Matcher<View> getConstraints() {
                return allOf(isDisplayed(), isAssignableFrom(EditText.class));
            }

            @Override
            public String getDescription() {
                return "select text range";
            }

            @Override
            public void perform(UiController uiController, View view) {
                EditText editText = (EditText) view;
                editText.setSelection(start, end);
            }
        };
    }
}
