# 🔑 Password Recovery - Quick Reference Guide

**Last Updated**: October 22, 2025  
**Status**: ✅ Production Ready

---

## 🚀 Quick Start

### For Users Who Forgot Password

1. **Go to**: Login page
2. **Click**: "Forgot Your Password?"
3. **Choose**: Email Recovery OR Recovery Key
4. **Follow**: On-screen instructions
5. **Done**: Login with new password

---

## 📋 Two Recovery Methods

### Method 1: Email Recovery (Simple)

```
1. Click "Email Recovery" tab
2. Enter your email
3. Click "Send Reset Link"
4. Check inbox
5. Follow email instructions
```

**Pros**: Simple, no setup needed  
**Cons**: Requires email access

---

### Method 2: Recovery Key (Recommended)

```
1. Click "Recovery Key" tab
2. Enter email + 24-char recovery key
3. Click "Continue"
4. Enter new master password
5. Confirm password
6. Click "Reset Password"
```

**Pros**: Secure, instant, offline-capable  
**Cons**: Requires one-time setup

---

## 🔧 Setting Up Recovery Key

### One-Time Setup (While Logged In)

```
1. Navigate to: /recovery-key-setup
2. Enter your email
3. Click "Generate Recovery Key"
4. SAVE the 24-character key securely:
   - Print it
   - Save in password manager
   - Store in safe
   - Give to trusted person
5. Verify you saved it
6. Done!
```

**⚠️ IMPORTANT**: Store recovery key separately from master password!

---

## 📍 URLs

- **Recovery Page**: `http://localhost:3000/password-recovery`
- **Setup Page**: `http://localhost:3000/recovery-key-setup`
- **Login Page**: `http://localhost:3000/`

---

## 🛡️ Security Features

✅ **Zero-knowledge**: Server never sees plaintext passwords  
✅ **Argon2id**: Strong key derivation  
✅ **Fresh salt**: New salt on every reset  
✅ **Strong validation**: 12+ chars, mixed case, numbers, special chars  
✅ **Vault re-encryption**: Secure data migration  

---

## 🎨 UI Components

### Email Recovery Tab
- Email input field
- "Send Reset Link" button
- Success message after submission

### Recovery Key Tab
- Email input field
- Recovery key input (24 chars with/without hyphens)
- Two-step process:
  1. Validate key
  2. Enter new password

### Success States
- ✅ Email sent confirmation
- ✅ Password reset success
- 🔄 Auto-redirect to login

---

## ⚠️ Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid recovery key or email" | Wrong key/email combo | Double-check both fields |
| "Passwords do not match" | Mismatch in confirmation | Re-enter passwords carefully |
| "Password must be at least 12 characters" | Too short | Use longer password |
| "Password must contain..." | Missing required chars | Add uppercase/lowercase/number/special |
| "No valid recovery key found" | Key not set up or wrong email | Check email or set up recovery key |

---

## 🔍 Troubleshooting

### "I lost my recovery key"

**Option 1**: Use email recovery instead  
**Option 2**: Contact support (if account recovery is set up)  
**Option 3**: If both lost, data cannot be recovered ⚠️

### "Email not arriving"

1. Check spam/junk folder
2. Wait 5-10 minutes
3. Verify email address is correct
4. Try resending

### "Recovery key not working"

1. Verify email is correct
2. Check for typos in recovery key
3. Try with/without hyphens
4. Ensure caps lock is off
5. Recovery key is case-sensitive

---

## 💡 Best Practices

### DO ✅
- Set up recovery key immediately after account creation
- Store recovery key in multiple secure locations
- Use different storage than master password
- Test recovery process once after setup
- Update recovery key if compromised
- Use strong new passwords on reset

### DON'T ❌
- Share recovery key via email/chat
- Store recovery key in plain text files
- Use same password as before
- Ignore password strength warnings
- Skip recovery key setup

---

## 🔐 Password Requirements

When resetting password, new password must have:

- ✅ Minimum 12 characters
- ✅ At least one uppercase letter (A-Z)
- ✅ At least one lowercase letter (a-z)
- ✅ At least one number (0-9)
- ✅ At least one special character (!@#$%^&*)

**Example Good Password**: `MySecure@Pass2025!`

---

## 🎯 Recovery Key Format

```
Format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
Example: AB3D-9KL2-QW8R-TY4U-MN7V-XZ5C

- 24 characters total
- 6 groups of 4 characters
- Separated by hyphens (optional when entering)
- Case-insensitive
- Characters: A-Z, 2-9 (no confusing chars like 0,O,1,I)
```

---

## 📊 Process Flow

### Email Recovery Flow
```
Login Page
    ↓
Forgot Password? → /password-recovery
    ↓
Email Recovery Tab
    ↓
Enter Email → Send Request
    ↓
Check Email → Follow Link
    ↓
Reset Password → Success
    ↓
Login with New Password
```

### Recovery Key Flow
```
Login Page
    ↓
Forgot Password? → /password-recovery
    ↓
Recovery Key Tab
    ↓
Enter Email + Key → Validate
    ↓
Enter New Password → Confirm
    ↓
Reset Success
    ↓
Login with New Password
```

---

## 🧪 Testing Checklist

- [ ] Can access password recovery page
- [ ] Email recovery sends email
- [ ] Recovery key validation works
- [ ] Can set new password
- [ ] Password validation works
- [ ] Error messages display correctly
- [ ] Success messages display
- [ ] Can login with new password
- [ ] Old password doesn't work
- [ ] Navigation buttons work
- [ ] Tab switching works

---

## 📱 Mobile Support

All features work on mobile:
- ✅ Responsive design
- ✅ Touch-friendly buttons
- ✅ Mobile-optimized forms
- ✅ Auto-zoom prevention
- ✅ Easy copy/paste for recovery key

---

## 🆘 Support

### Need Help?
- **Documentation**: See full guide in README.md
- **Bug Report**: Create GitHub issue
- **Questions**: Check FAQ section
- **Emergency**: Contact support team

### Common Questions

**Q: Is my data safe during recovery?**  
A: Yes! All encryption happens client-side. Server never sees plaintext data.

**Q: How many times can I use recovery key?**  
A: Unlimited. But consider generating new one after use for security.

**Q: Can I have multiple recovery keys?**  
A: Currently one per account. Future feature planned.

**Q: What if someone steals my recovery key?**  
A: They still need your email. But generate new key immediately if compromised.

---

## 📅 Version History

- **v1.0** (Oct 22, 2025): Initial release
  - Email recovery
  - Recovery key recovery
  - Modern UI
  - Strong security

---

## ✅ Quick Validation

Before considering password recovery working, verify:

1. ✅ Can access `/password-recovery` page
2. ✅ Both tabs (Email/Key) visible and working
3. ✅ Recovery key validation endpoint responds
4. ✅ Password reset completes successfully
5. ✅ Can login with new password
6. ✅ Error handling works correctly
7. ✅ No console errors
8. ✅ UI is responsive

---

**Ready to Use!** 🎉

For detailed technical documentation, see:
- `BUG_FIXES_AND_IMPROVEMENTS.md`
- `README.md`
- Component documentation in code

---

**Created**: October 22, 2025  
**Author**: SecureVault Development Team  
**Status**: ✅ Production Ready

