# Shared Folders Quick Reference Guide

## 🚀 Quick Start

Access the Shared Folders feature:
```
http://localhost:3000/shared-folders
```

---

## 🎯 Features Overview

### 1. Dashboard View
- View all your shared folders
- Filter by: All | Owned by Me | Shared with Me
- See pending invitations count
- Quick refresh button

### 2. Create Folder
Click **"Create Folder"** button to:
- Set folder name (required)
- Add description (optional)
- Enable 2FA requirement (optional)

### 3. Folder Management
Click any folder card to:
- View/manage members
- Send invitations
- Change member roles
- Remove members
- Delete folder (owners only)

### 4. Invitations
Click **"Invitations"** button (when you have pending invitations) to:
- View all pending invitations
- Accept invitations
- Decline invitations

---

## 👥 Roles & Permissions

### Owner
- Full control over the folder
- Can manage all members
- Can change any member's role
- Can delete the folder
- Cannot be removed or have role changed

### Admin
- Can invite new members
- Can change roles (except Owner)
- Can remove members (except Owner)
- Cannot delete the folder

### Editor
- Can view and edit items in the folder
- Can add new items
- Cannot manage members
- Cannot change settings

### Viewer
- Read-only access
- Can view items
- Cannot edit or add items
- Cannot manage members

---

## 🎨 UI Components

### CreateFolderModal
**Purpose:** Create new shared folders

**Fields:**
- Folder Name* (required)
- Description (optional)
- Require 2FA (checkbox)

**Actions:**
- Cancel
- Create Folder

### FolderDetailsModal
**Purpose:** Manage folder and members

**Tabs:**
1. **Members Tab**
   - Invite form (email + role)
   - Member list with avatars
   - Role dropdowns (for admins/owners)
   - Remove buttons

2. **Settings Tab**
   - Danger Zone (delete folder)

### InvitationsModal
**Purpose:** Accept/decline folder invitations

**Shows:**
- Folder name and icon
- Inviter name
- Your assigned role
- 2FA requirement status
- Time sent

**Actions:**
- Accept
- Decline

---

## 🔒 Security Features

### End-to-End Encryption
- All folder contents are encrypted
- Keys shared securely between members
- Zero-knowledge architecture

### 2FA Enforcement
- Optional per-folder
- Members must verify identity with 2FA
- Additional security for sensitive folders

### Role-Based Access
- Granular permission control
- Prevent unauthorized actions
- Audit-friendly structure

---

## 📱 User Flows

### Creating a Folder
```
1. Click "Create Folder"
2. Enter folder name
3. (Optional) Add description
4. (Optional) Enable 2FA requirement
5. Click "Create Folder"
6. ✅ Folder created!
```

### Inviting Members
```
1. Click on a folder
2. Go to "Members" tab
3. Enter email address
4. Select role (Viewer/Editor/Admin)
5. Click "Invite"
6. ✅ Invitation sent!
```

### Accepting Invitation
```
1. Click "Invitations" button
2. Review invitation details
3. Click "Accept"
4. ✅ Folder added to your list!
```

### Removing a Member
```
1. Click on a folder (must be Owner/Admin)
2. Go to "Members" tab
3. Click trash icon next to member
4. Confirm removal
5. ✅ Member removed!
```

### Deleting a Folder
```
1. Click on a folder (must be Owner)
2. Go to "Settings" tab
3. Click "Delete Folder" in Danger Zone
4. Confirm deletion
5. ✅ Folder deleted!
```

---

## 🎨 Visual Indicators

### Badges
- 🔵 **Owner** - Blue badge
- 🟣 **Admin** - Purple badge
- 🟢 **Editor** - Green badge
- ⚫ **Viewer** - Gray badge
- 🟡 **2FA Required** - Orange badge with shield icon

### Icons
- 📁 **Folder** - Standard folder (no 2FA)
- 🔒 **Lock** - 2FA-protected folder
- 👥 **Users** - Member count
- ✉️ **Mail** - Invitations
- ⚠️ **Alert** - Warnings/errors

---

## 🔧 API Endpoints Used

```javascript
// Get all folders
GET /api/vault/shared-folders/

// Create folder
POST /api/vault/shared-folders/

// Get folder members
GET /api/vault/shared-folders/:id/members/

// Invite member
POST /api/vault/shared-folders/:id/invite/

// Update member role
PATCH /api/vault/shared-folders/:id/members/:memberId/

// Remove member
DELETE /api/vault/shared-folders/:id/members/:memberId/

// Delete folder
DELETE /api/vault/shared-folders/:id/

// Get pending invitations
GET /api/vault/shared-folders/invitations/pending/

// Accept invitation
POST /api/vault/shared-folders/invitations/:id/accept/

// Decline invitation
POST /api/vault/shared-folders/invitations/:id/decline/
```

---

## 💡 Pro Tips

1. **Use 2FA for Sensitive Folders**
   - Enable 2FA requirement for folders with sensitive data
   - Adds extra security layer

2. **Assign Roles Carefully**
   - Start with Viewer role
   - Upgrade to Editor/Admin as needed
   - Keep Owner role exclusive

3. **Use Descriptions**
   - Add folder descriptions
   - Helps team understand purpose
   - Improves organization

4. **Regular Reviews**
   - Review members periodically
   - Remove inactive members
   - Update roles as needed

5. **Accept Invitations Promptly**
   - Check invitations regularly
   - Accept or decline quickly
   - Keeps things organized

---

## 🐛 Troubleshooting

### Issue: Can't see shared folders
**Solution:** Make sure you're authenticated. Navigate to `/shared-folders` route.

### Issue: Can't invite members
**Solution:** Check you have Owner or Admin role. Only these roles can invite.

### Issue: Can't change a member's role
**Solution:** Verify you're Owner/Admin and the member is not the Owner.

### Issue: Invitation not showing
**Solution:** Check the invitations modal by clicking the "Invitations" button.

### Issue: Can't delete folder
**Solution:** Only the Owner can delete folders. Check your role.

---

## 🎯 Best Practices

### Folder Organization
- Use clear, descriptive names
- Add meaningful descriptions
- Group related items together
- Use consistent naming conventions

### Member Management
- Invite only necessary members
- Use minimum required permissions
- Review access regularly
- Remove members who leave team

### Security
- Enable 2FA for sensitive folders
- Use strong, unique passwords
- Review folder activity regularly
- Don't share Owner role unnecessarily

---

## 📊 Status Indicators

### Folder Card States
- **Normal** - White background, gray border
- **Hover** - Subtle shadow, slight lift
- **Loading** - Spinner or disabled state
- **Error** - Red border, error message

### Button States
- **Primary** - Blue background
- **Secondary** - Gray background
- **Danger** - Red background
- **Disabled** - Faded, no interaction

### Loading States
- **Accepting...** - When accepting invitation
- **Declining...** - When declining invitation
- **Creating...** - When creating folder
- **Sending...** - When sending invitation

---

## 🎨 Keyboard Shortcuts

- `Esc` - Close any open modal
- `Enter` - Submit active form
- `Tab` - Navigate between fields
- `Space` - Toggle checkboxes

---

## 📱 Mobile Responsiveness

All components are fully responsive:
- Adapts to screen size
- Touch-friendly buttons
- Optimized layouts
- Accessible on all devices

---

## ✨ Key Features

### Real-Time Updates
- Instant feedback on actions
- Toast notifications
- Auto-refresh after changes

### Error Handling
- Clear error messages
- Inline validation
- Helpful error descriptions

### User Experience
- Intuitive interface
- Clear visual hierarchy
- Smooth animations
- Accessible design

---

*Last Updated: October 25, 2025*
*Version: 1.0*

