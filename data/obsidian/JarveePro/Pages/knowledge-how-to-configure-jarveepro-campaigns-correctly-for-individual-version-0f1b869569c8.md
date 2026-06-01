---
title: "How to Configure JarveePro Campaigns Correctly for Individual Version Users"
source_url: "https://blog.jarveepro.com/knowledge/JarveePro-Campaign-Settings/How-to-Configure-JarveePro-Campaigns-Correctly-for-Individual-Version-Users/8804"
category: "knowledge"
fetched_at: "2026-05-29T15:10:26+00:00"
status_code: 200
content_hash: "c79308ecd21e2e6e5d371c5d6fa86bcd9c494d5a"
tags: ["jarveepro", "jarveepro/knowledge"]
---

# How to Configure JarveePro Campaigns Correctly for Individual Version Users

Source: [https://blog.jarveepro.com/knowledge/JarveePro-Campaign-Settings/How-to-Configure-JarveePro-Campaigns-Correctly-for-Individual-Version-Users/8804](https://blog.jarveepro.com/knowledge/JarveePro-Campaign-Settings/How-to-Configure-JarveePro-Campaigns-Correctly-for-Individual-Version-Users/8804)

Category: `knowledge`

## Summary

How to Configure JarveePro Campaigns Correctly for Individual Version Users

## Headings

- How to Configure JarveePro Campaigns Correctly for Individual Version Users
- How to Send One Unique Facebook Message Per User with One Account in JarveePro Individual Version
- Understanding the Real Problem
- The Correct Configuration for Individual Version Users
- Correct “Profile URLs” Tab Settings
- Times Allowed per Profile
- Times Allowed per Profile by Account
- Correct “Messages” Tab Settings
- Times Allowed per Message
- Times Allowed per Message by Account
- Why Older Tutorials May Confuse Individual Users
- Recommended Setup Summary
- Profile URLs Tab
- Messages Tab
- Conclusion

## Content

How to Configure JarveePro Campaigns Correctly for Individual Version Users

2026-05-15

How to Send One Unique Facebook Message Per User with One Account in JarveePro Individual Version

Many older JarveePro knowledge base articles were originally written for Full Version, Business Version, or Enterprise users running multiple Facebook accounts at the same time.

Because of that, many tutorials focused heavily on:

Preventing the same account from repeatedly messaging users

Rotating messages across multiple accounts

Limiting duplicate outreach behavior

Distributing campaigns between dozens or hundreds of accounts

However, the situation is very different for users running the

JarveePro Individual Version

With the Individual Plan, users can only connect:

1 Facebook account

1 sending profile

This changes how the messaging limits should be configured completely.

A common mistake happens when users apply “multi-account” settings to a “single-account” setup. This often causes campaigns to stop early after sending only a few messages.

This guide explains the correct setup for users who:

Only have 1 Facebook account

Want to send messages to many profile URLs

Want each target user to receive only one message

Do not want duplicate sending

Want the campaign to finish the full profile list successfully

Understanding the Real Problem

Many users incorrectly configure limits like:

1–100

1–50

1–10

for:

Times Allowed per Profile by Account

Times Allowed per Message

Times Allowed per Message by Account

The problem is:

These are

ranges

, not fixed values.

So if the setting is:

JarveePro may randomly choose:

25

or any value inside that range.

This is exactly why some campaigns suddenly stop after sending only:

3 messages

5 messages

8 messages

even when there are still dozens of profile URLs remaining.

The software is following the configured range correctly.

The Correct Configuration for Individual Version Users

If you only have:

1 Facebook account

1 message template

Many target profile URLs

then you should use

fixed values

, not random ranges.

For example:

If you want to message:

100 Facebook profile URLs

then all related limits should be configured as:

100 – 100

NOT:

1 – 100

This forces JarveePro to consistently allow the full campaign completion instead of randomly stopping early.

Correct “Profile URLs” Tab Settings

Inside the

Profile URLs

tab:

Times Allowed per Profile

Set:

1 – 1

This ensures:

Each target profile receives the message only once

No duplicate messaging occurs

Times Allowed per Profile by Account

Why?

Because:

You only have one sending account

That single account must be allowed to process all 100 profiles

Correct “Messages” Tab Settings

Inside the

Messages

tab, all limits should also use fixed values.

If your campaign targets:

100 profile URLs

then configure:

Times Allowed per Message

100 – 100

Times Allowed per Message by Account

(bottom section)

This ensures:

Your one message template can be reused across all 100 targets

The single account is allowed to fully complete the campaign

No random early stopping happens

Why Older Tutorials May Confuse Individual Users

Most older tutorials were designed for:

Full Version users

Agency users

Multi-account environments

Enterprise automation setups

Those users usually wanted:

Different accounts sending different messages

Strict anti-duplication limits

Account rotation behavior

Large-scale distribution systems

But Individual Version users have a very different workflow.

With only one connected Facebook account:

You are not distributing work across accounts

You are not rotating messages

You simply want one account to finish the entire profile list

That means your settings should focus on:

Fixed allocation

Stable completion

No randomization

Recommended Setup Summary

If you have:

1 Facebook account

1 message template

100 target profiles

then use:

Profile URLs Tab

Times Allowed per Profile → 1 – 1

Times Allowed per Profile by Account → 1 – 1

Messages Tab

Times Allowed per Message → 100 – 100

Times Allowed per Message by Account → 100 – 100

Bottom Times Allowed per Message → 100 – 100

This configuration allows:

One unique message per user

No duplicate messaging

Full campaign completion

Stable behavior for Individual Version users

Conclusion

JarveePro is highly flexible because it supports both:

Single-account users

Enterprise-scale automation users

However, using the wrong configuration style for your account type can easily create unexpected campaign behavior.

If you are using the Individual Version, avoid random ranges for messaging limits unless you intentionally want randomized stopping behavior.

For single-account outreach campaigns, fixed values like:

100 – 100

are the safest and most reliable approach for completing the full target profile list successfully.

## Extracted Links

- https://blog.jarveepro.com/Home/Blog
- https://blog.jarveepro.com/Home/KnowledgeBaseList
- https://blog.jarveepro.com/knowledge/JarveePro-Campaign-Settings/How-to-Configure-JarveePro-Campaigns-Correctly-for-Individual-Version-Users/8804
- https://twitter.com/share?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Campaign-Settings%2FHow-to-Configure-JarveePro-Campaigns-Correctly-for-Individual-Version-Users%2F8804
- https://www.facebook.com/jarveeproadmin
- https://www.facebook.com/sharer/sharer.php?u=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Campaign-Settings%2FHow-to-Configure-JarveePro-Campaigns-Correctly-for-Individual-Version-Users%2F8804
- https://www.jarveepro.com/
- https://www.jarveepro.com/all-features.html
- https://www.jarveepro.com/contact-us.html
- https://www.jarveepro.com/contact.html
- https://www.jarveepro.com/discord-features.html
- https://www.jarveepro.com/facebook-features.html
- https://www.jarveepro.com/get-now.html
- https://www.jarveepro.com/instagram-features.html
- https://www.jarveepro.com/linkedIn-features.html
- https://www.jarveepro.com/pinterest-features.html
- https://www.jarveepro.com/pricing.html
- https://www.jarveepro.com/reddit-features.html
- https://www.jarveepro.com/tiktok-features.html
- https://www.jarveepro.com/tumblr-features.html
- https://www.jarveepro.com/twitter-features.html
- https://www.jarveepro.com/videos-tutorials.html
- https://www.jarveepro.com/whatsapp-features.html
- https://www.jarveepro.com/youtube-features.html
- https://www.pinterest.com/pin/create/button/?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Campaign-Settings%2FHow-to-Configure-JarveePro-Campaigns-Correctly-for-Individual-Version-Users%2F8804
