#include <asm/io.h>
#include <asm/set_memory.h>

#include <linux/mm.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/init.h>
#include <linux/delay.h>
#include <linux/ioport.h>
#include <linux/device.h>
#include <linux/module.h>

#define COMMON_VCI_PREVENT_INCLUDES
#include "common/include/vci-msg.h"

#define PIM_REGION_START 0x800000000
#define PIM_REGION_SIZE 0x200000000 * 40
#define RANK_SIZE 0x200000000
#define RANK_STRIDE 1
#define RANK_COUNT 40
#define VPIM_CDEV_MAJOR 240

MODULE_AUTHOR("Fabian van Rissenbeck");
MODULE_DESCRIPTION("Driver for PIM ranks passed via QEMU");
MODULE_LICENSE("GPL");

struct vpim_rank {
    struct cdev dev;
    struct device* pdev;
    unsigned minor;
    bool available;
    bool used;
};

static struct {
    struct resource root_region;
    void __iomem* root_mem;
    struct class* vpim_class;
    struct vpim_rank dev_list[RANK_COUNT];
} g_vpim_state = { 0 };

static int vpim_open(struct inode* inode, struct file* file);

static int vpim_release(struct inode* inode, struct file* file);

static int vpim_mmap(struct file* file, struct vm_area_struct* vma);

static vm_fault_t vpim_fault(struct vm_fault* vmf);

static const struct file_operations vpim_fops = {
    .owner = THIS_MODULE,
    .open = vpim_open,
    .release = vpim_release,
    .mmap = vpim_mmap,
};

static const struct vm_operations_struct vpim_vm_ops = {
    .fault = vpim_fault,
};

static void vpim_discover_ranks(DECLARE_BITMAP(bm, RANK_COUNT)) {
    bitmap_zero(bm, RANK_COUNT);

    for (int i = 0; i < 40; ++i) {
        uint8_t __iomem* base = g_vpim_state.root_mem;
        base += RANK_SIZE * RANK_STRIDE * i;

        uint64_t __iomem* ci = (uint64_t __iomem*)(base + 0x20000);
        vci_msg msg = { .type = VCI_PRESENT };

        writeq(vci_msg_to_qword(msg), ci);
    }

    msleep(10);

    for (int i = 0; i < 40; ++i) {
        uint8_t __iomem* base = g_vpim_state.root_mem;
        base += RANK_SIZE * RANK_STRIDE * i;

        uint64_t __iomem* ci = (uint64_t __iomem*)(base + 0x20000);
        vci_msg msg = vci_msg_from_qword(readq(ci));

        if (msg.type == VCI_IS_PRESENT) {
            set_bit(i, bm);
        }
    }
}

static int __init vpim_device_init(void) {
    int err;

    g_vpim_state.root_region = (struct resource) {
        .name = "VPIM Root",
        .start = PIM_REGION_START,
        .end = PIM_REGION_START + PIM_REGION_SIZE - 1,
        .flags = IORESOURCE_MEM | IORESOURCE_MEM_64
    };

    if ((err = request_resource(&iomem_resource, &g_vpim_state.root_region)) < 0) {
        pr_warn("cannot acquire vpim root region\n");
        goto end;
    }

    g_vpim_state.root_mem = ioremap(PIM_REGION_START, PIM_REGION_SIZE);

    if (g_vpim_state.root_mem == NULL) {
        pr_warn("cannot ioremap pim root region\n");
        goto cleanup_resource;
    }

    g_vpim_state.vpim_class = class_create(THIS_MODULE, "vpim");

    if (IS_ERR(g_vpim_state.vpim_class)) {
        pr_warn("cannot create vpim class\n");
        goto cleanup_mem;
    }

    if ((err = register_chrdev_region(MKDEV(VPIM_CDEV_MAJOR, 0), RANK_COUNT, "vpim"))) {
        pr_warn("cannot register chrdev region\n");
        goto cleanup_class;
    }

    DECLARE_BITMAP(avl_ranks, 40);
    vpim_discover_ranks(avl_ranks);

    for (int i = 0; i < RANK_COUNT; ++i) {
        if (!test_bit(i, avl_ranks)) {
            continue;
        }

        g_vpim_state.dev_list[i] = (struct vpim_rank) {
            .minor = i,
            .used = false,
            .pdev = NULL
        };

        cdev_init(&g_vpim_state.dev_list[i].dev, &vpim_fops);

        if ((err = cdev_add(&g_vpim_state.dev_list[i].dev, MKDEV(VPIM_CDEV_MAJOR, i), 1)) < 0) {
            pr_warn("cannot add cdev device %u.%u\n", VPIM_CDEV_MAJOR, i);
            goto cleanup_dev_list;
        }

        g_vpim_state.dev_list[i].pdev = device_create(
            g_vpim_state.vpim_class,
            NULL, MKDEV(VPIM_CDEV_MAJOR, i), NULL,
            "vpim%d", i
        );

        if (IS_ERR(g_vpim_state.dev_list[i].pdev)) {
            cdev_del(&g_vpim_state.dev_list[i].dev);
            pr_warn("cannot create device listing /dev/vpim%u for device %u.%u\n", i, VPIM_CDEV_MAJOR, i);

            goto cleanup_dev_list;
        }

        g_vpim_state.dev_list[i].available = true;
    }

    return 0;

cleanup_dev_list:
    for (int j = 0; j < RANK_COUNT; ++j) {
        if (g_vpim_state.dev_list[j].available) {
            device_destroy(g_vpim_state.vpim_class, MKDEV(VPIM_CDEV_MAJOR, j));
            cdev_del(&g_vpim_state.dev_list[j].dev);
        }
    }

    unregister_chrdev_region(MKDEV(VPIM_CDEV_MAJOR, 0), RANK_COUNT);

cleanup_class:
    class_destroy(g_vpim_state.vpim_class);

cleanup_mem:
    iounmap(g_vpim_state.root_mem);

cleanup_resource:
    release_resource(&g_vpim_state.root_region);

end:
    return err;
}

static void __exit vpim_device_exit(void) {
    for (int j = 0; j < RANK_COUNT; ++j) {
        if (g_vpim_state.dev_list[j].available) {
            device_destroy(g_vpim_state.vpim_class, MKDEV(VPIM_CDEV_MAJOR, j));
            cdev_del(&g_vpim_state.dev_list[j].dev);
        }
    }

    unregister_chrdev_region(MKDEV(VPIM_CDEV_MAJOR, 0), RANK_COUNT);
    class_destroy(g_vpim_state.vpim_class);
    iounmap(g_vpim_state.root_mem);
    release_resource(&g_vpim_state.root_region);
}

static int vpim_open(struct inode* inode, struct file* file) {
    struct vpim_rank* rank = container_of(inode->i_cdev, struct vpim_rank, dev);

    if (rank->used) {
        return -EBUSY;
    }

    if (!rank->available) {
        return -ENOENT;
    }

    file->private_data = rank;
    rank->used = true;

    return 0;
}

static int vpim_release(struct inode* inode, struct file* file) {
    struct vpim_rank* rank = container_of(inode->i_cdev, struct vpim_rank, dev);

    rank->used = false;
    return 0;
}

static vm_fault_t vpim_fault(struct vm_fault* vmf) {
    struct vpim_rank* rank = vmf->vma->vm_file->private_data;

    unsigned long addr = vmf->address;
    unsigned long rank_base = PIM_REGION_START + rank->minor * RANK_STRIDE * RANK_SIZE;
    unsigned long rel_pfn = (addr >> PAGE_SHIFT) - (vmf->vma->vm_start >> PAGE_SHIFT);

    BUG_ON(rel_pfn >= (RANK_SIZE >> PAGE_SHIFT));
    BUG_ON(rank_base >= PIM_REGION_START + PIM_REGION_SIZE);

    pr_info("Mapping page %u.%lu into address space\n", rank->minor, rel_pfn);

    unsigned long pfn = (rank_base >> PAGE_SHIFT) + rel_pfn;
    return vmf_insert_pfn_prot(vmf->vma, addr, pfn, pgprot_noncached(vmf->vma->vm_page_prot));
}

static int vpim_mmap(struct file* file, struct vm_area_struct* vma) {
    size_t sz = vma->vm_end - vma->vm_start;

    if (sz != 0x200000000) {
        return -EINVAL;
    }

    vma->vm_ops = &vpim_vm_ops;
    vma->vm_flags |= VM_PFNMAP;

    if (is_cow_mapping(vma->vm_flags)) {
        pr_warn("VM_SHARED not set\n");
    }

    vma->vm_flags |= VM_SHARED;
    return 0;
}

module_init(vpim_device_init);
module_exit(vpim_device_exit);

